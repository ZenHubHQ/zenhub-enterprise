#!/usr/bin/env python3
"""Gateway bucket proxy must verify the object-storage certificate.

The nginx-gateway serves /files/, /images/, and /zhe-public/ff-ext-signed/
on the main Zenhub hostname. Each location proxies to the uploads bucket
over HTTPS. These tests render that configuration the way image
nginx:1.31.8-trixie does, then request those URLs from a bucket peer.

They fail while the gateway accepts an untrusted or wrong-name certificate
and returns or caches that peer's body. They pass when every bucket
location verifies the certificate against its trust bundle and requires the
certificate to match the bucket hostname.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
GATEWAY_CONFIGMAPS = REPO / "k8s-cluster/base/gateway/configmaps.yaml"
BASE_KUSTOMIZATION = REPO / "k8s-cluster/base/kustomization.yaml"
DEPLOYED_TLS = REPO / "k8s-cluster/base/non-dynamic/tls"
UNUSED_TLS = REPO / "k8s-cluster/base/tls"

NGINX_SRC = Path("/tmp/nginx-release-1.31.8")
NGINX_BIN = NGINX_SRC / "objs/nginx"
NGINX_VERSION = "1.31.8"
NGINX_TARBALL_URL = (
    "https://github.com/nginx/nginx/archive/refs/tags/release-1.31.8.tar.gz"
)

BUCKET_IP = "10.88.0.2"
GATEWAY_IP = "10.88.0.1"
FILES_HOST = "files-bucket.bucket.test"
IMAGES_HOST = "images-bucket.bucket.test"
MARKER_ATTACK = "ZH-UNTRUSTED-BUCKET-BODY"
MARKER_LEGIT = "ZH-TRUSTED-BUCKET-BODY"
CACHE_PATH = "/files/cached-object"
PUBLIC_PATHS = (
    "/files/issue-attachment",
    "/images/avatar.png",
    "/zhe-public/ff-ext-signed/latest.json",
)

# Same names the gateway deployment injects before the image entrypoint
# runs envsubst. The bucket hostnames are test fixtures, not product values.
TEMPLATE_ENV = {
    "FILES_BUCKET_NAME": "files-bucket",
    "IMAGES_BUCKET_NAME": "images-bucket",
    "BUCKET_DOMAIN": "bucket.test",
    "FIREFOX_EXT_S3_BUCKET_DIR": "ff-extension",
    "WEBAPP": "127.0.0.1:9",
    "API": "127.0.0.1:9",
    "WEBHOOK": "127.0.0.1:9",
    "ACTIONCABLE": "127.0.0.1:9",
    "RAPTORAPI": "127.0.0.1:9",
    "RAPTORADMIN": "127.0.0.1:9",
    "SOCKET": "127.0.0.1:9",
}


def _run(cmd, **kwargs):
    if cmd and cmd[0] == "ip":
        cmd = ["/usr/sbin/ip", *cmd[1:]]
    return subprocess.run(cmd, check=True, **kwargs)


def _ensure_root():
    if os.geteuid() == 0:
        return
    os.execvp("sudo", ["sudo", "-E", sys.executable, *sys.argv])


def _ensure_nginx() -> Path:
    if NGINX_BIN.exists():
        version = subprocess.run(
            [str(NGINX_BIN), "-V"], capture_output=True, text=True
        )
        details = version.stderr + version.stdout
        if (
            f"nginx/{NGINX_VERSION}" in details
            and "--prefix=/etc/nginx" in details
            and "--with-http_ssl_module" in details
            and "--with-http_v2_module" in details
        ):
            return NGINX_BIN
    tarball = Path("/tmp/nginx-1.31.8.tar.gz")
    if not NGINX_SRC.exists():
        subprocess.run(
            ["curl", "-fsSL", "-o", str(tarball), NGINX_TARBALL_URL], check=True
        )
        subprocess.run(["tar", "-xzf", str(tarball), "-C", "/tmp"], check=True)
    subprocess.run(
        [
            "./auto/configure",
            "--prefix=/etc/nginx",
            "--sbin-path=/tmp/nginx-1.31.8/sbin/nginx",
            "--conf-path=/etc/nginx/nginx.conf",
            "--error-log-path=/var/log/nginx/error.log",
            "--http-log-path=/var/log/nginx/access.log",
            "--pid-path=/var/run/nginx.pid",
            "--lock-path=/var/run/nginx.lock",
            "--http-client-body-temp-path=/var/cache/nginx/client_temp",
            "--http-proxy-temp-path=/var/cache/nginx/proxy_temp",
            "--http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp",
            "--http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp",
            "--http-scgi-temp-path=/var/cache/nginx/scgi_temp",
            "--user=nginx",
            "--group=nginx",
            "--with-http_ssl_module",
            "--with-http_v2_module",
            "--with-http_realip_module",
            "--with-threads",
        ],
        cwd=NGINX_SRC,
        check=True,
    )
    subprocess.run(["make", "-j", str(os.cpu_count() or 2)], cwd=NGINX_SRC, check=True)
    return NGINX_BIN


def _load_documents(path: Path):
    return [doc for doc in yaml.safe_load_all(path.read_text()) if doc]


def _configmap(docs, name):
    for doc in docs:
        if doc.get("kind") == "ConfigMap" and doc.get("metadata", {}).get("name") == name:
            return doc
    raise AssertionError(f"configmap {name} not found")


def _template_files(tls_dir: Path) -> dict[str, str]:
    kustomization = yaml.safe_load((tls_dir / "kustomization.yaml").read_text())
    selected = {}
    for generator in kustomization.get("configMapGenerator", []):
        for filename in generator.get("files", []):
            if filename.endswith(".template") or filename == "include-ssl.conf":
                selected[filename] = (tls_dir / filename).read_text()
    gateway_docs = _load_documents(GATEWAY_CONFIGMAPS)
    gateway = _configmap(gateway_docs, "zhe-gw-conf")
    selected["default.conf.template"] = gateway["data"]["default.conf.template"]
    nginx_conf = _configmap(gateway_docs, "zhe-gw-nginx-conf")["data"]["nginx.conf"]
    include_ssl = selected.pop("include-ssl.conf")
    return {
        "nginx_conf": nginx_conf,
        "include_ssl": include_ssl,
        "templates": selected,
    }


def _envsubst(templates: dict[str, str], output_dir: Path):
    """Match docker-nginx 1.31.8 entrypoint/20-envsubst-on-templates.sh."""
    env = os.environ.copy()
    env.update(TEMPLATE_ENV)
    defined = " ".join("${%s}" % name for name in env)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in templates.items():
        if not name.endswith(".template"):
            raise AssertionError(name)
        dest = output_dir / name[: -len(".template")]
        proc = subprocess.run(
            ["envsubst", defined],
            input=text.encode(),
            capture_output=True,
            check=True,
            env=env,
        )
        dest.write_bytes(proc.stdout)


def _openssl(args):
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def _make_ca(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    key = directory / "ca.key"
    crt = directory / "ca.crt"
    _openssl([
        "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(key), "-out", str(crt), "-days", "2",
        "-subj", "/CN=FixtureBucketCA",
    ])
    return crt, key


def _make_cert(directory: Path, common_name: str, sans: list[str], ca):
    directory.mkdir(parents=True, exist_ok=True)
    key = directory / "tls.key"
    crt = directory / "tls.crt"
    san = "subjectAltName=" + ",".join(f"DNS:{name}" for name in sans)
    if ca is None:
        _openssl([
            "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(crt), "-days", "2",
            "-subj", f"/CN={common_name}", "-addext", san,
        ])
    else:
        ca_crt, ca_key = ca
        csr = directory / "tls.csr"
        ext = directory / "san.cnf"
        ext.write_text(san + "\n")
        _openssl([
            "req", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(csr),
            "-subj", f"/CN={common_name}", "-addext", san,
        ])
        _openssl([
            "x509", "-req", "-in", str(csr),
            "-CA", str(ca_crt), "-CAkey", str(ca_key), "-CAcreateserial",
            "-out", str(crt), "-days", "2", "-extfile", str(ext),
        ])
    return crt, key


def _trusted_certificate_paths(conf_dir: Path) -> list[Path]:
    paths = []
    for conf in conf_dir.glob("*.conf"):
        for line in conf.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "proxy_ssl_trusted_certificate" not in stripped:
                continue
            value = stripped.split("proxy_ssl_trusted_certificate", 1)[1].strip().rstrip(";").strip()
            if not value or value.startswith("#"):
                continue
            path = Path(value)
            if not path.is_absolute():
                path = Path("/etc/nginx") / path
            paths.append(path)
    return paths


def _install_trust(conf_dir: Path, ca_cert: Path, saved: dict[Path, bytes | None]):
    pem = ca_cert.read_bytes()
    for path in _trusted_certificate_paths(conf_dir):
        if path in saved:
            continue
        saved[path] = path.read_bytes() if path.exists() else None
        current = saved[path] or b""
        if pem not in current:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(current + b"\n" + pem + b"\n")


def _restore_trust(saved: dict[Path, bytes | None]):
    for path, previous in saved.items():
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)


class BucketPeer:
    def __init__(self, work: Path, cert: Path, key: Path, marker: str):
        self.work = work
        self.cert = cert
        self.key = key
        self.marker = marker
        self.proc = None

    def start(self):
        script = self.work / "bucket_peer.py"
        script.write_text(textwrap.dedent(f'''\
            import ssl, sys
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            marker = open(sys.argv[3], "r", encoding="utf-8").read()
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    body = marker.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "public, max-age=600")
                    self.send_header("Set-Cookie", "injected=1")
                    self.end_headers()
                    self.wfile.write(body)
                def log_message(self, fmt, *args):
                    return
            httpd = ThreadingHTTPServer(("{BUCKET_IP}", 443), Handler)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(sys.argv[1], sys.argv[2])
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
            httpd.serve_forever()
        '''))
        marker_path = self.work / "marker.txt"
        marker_path.write_text(self.marker)
        self.proc = subprocess.Popen(
            [
                "/usr/sbin/ip", "netns", "exec", "bucket",
                sys.executable, str(script), str(self.cert), str(self.key), str(marker_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.proc.poll() is not None:
                output = self.proc.stdout.read() if self.proc.stdout else ""
                raise RuntimeError(f"bucket peer exited: {output}")
            try:
                stream = socket.create_connection((BUCKET_IP, 443), 0.2)
            except OSError:
                time.sleep(0.05)
                continue
            stream.close()
            return
        raise RuntimeError("bucket peer did not listen")

    def stop(self):
        if self.proc is None or self.proc.poll() is not None:
            if self.proc is not None and self.proc.stdout:
                self.proc.stdout.close()
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)
        if self.proc.stdout:
            self.proc.stdout.close()


def _fetch(path: str) -> tuple[str, str, str]:
    stream = socket.create_connection(("127.0.0.1", 80), 5)
    stream.sendall(
        f"GET {path} HTTP/1.1\r\nHost: zenhub.example\r\nConnection: close\r\n\r\n".encode()
    )
    data = b""
    while True:
        chunk = stream.recv(65536)
        if not chunk:
            break
        data += chunk
    stream.close()
    head, _, body = data.partition(b"\r\n\r\n")
    header_text = head.decode(errors="replace")
    status = header_text.splitlines()[0]
    return status, header_text, body.decode(errors="replace")


def _reset_cache():
    for path in (Path("/tmp/files"), Path("/tmp/images")):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir()
        os.chmod(path, 0o777)


def _start_nginx(binary: Path):
    subprocess.run([str(binary), "-s", "stop"], check=False, capture_output=True)
    time.sleep(0.1)
    check = subprocess.run([str(binary), "-t"], capture_output=True, text=True)
    if check.returncode != 0:
        raise AssertionError(f"nginx -t failed\n{check.stderr}")
    subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            stream = socket.create_connection(("127.0.0.1", 80), 0.2)
        except OSError:
            time.sleep(0.05)
            continue
        stream.close()
        return
    raise AssertionError("nginx did not listen on port 80")


def _stop_nginx(binary: Path):
    subprocess.run([str(binary), "-s", "stop"], check=False, capture_output=True)
    time.sleep(0.1)


def _error_log_tail() -> str:
    path = Path("/var/log/nginx/error.log")
    if not path.exists():
        return ""
    lines = path.read_text(errors="replace").splitlines()
    return "\n".join(lines[-30:])


class GatewayBucketUpstreamTLSTest(unittest.TestCase):
    work: Path
    nginx: Path
    trust_saved: dict

    @classmethod
    def setUpClass(cls):
        _ensure_root()
        base = yaml.safe_load(BASE_KUSTOMIZATION.read_text())
        resources = base.get("resources", [])
        if "non-dynamic/tls" not in resources:
            raise AssertionError(
                "k8s-cluster/base/kustomization.yaml does not deploy non-dynamic/tls"
            )
        cls.nginx = _ensure_nginx()
        cls.work = Path("/tmp/zhe-gateway-tls-test")
        if cls.work.exists():
            shutil.rmtree(cls.work)
        cls.work.mkdir()
        cls.trust_saved = {}
        cls._prepare_host()
        ca = _make_ca(cls.work / "ca")
        cls.ca_cert = ca[0]
        cls.certs = {
            "self-signed": _make_cert(
                cls.work / "self-signed",
                FILES_HOST,
                [FILES_HOST, IMAGES_HOST],
                None,
            ),
            "legit": _make_cert(
                cls.work / "legit",
                FILES_HOST,
                [FILES_HOST, IMAGES_HOST],
                ca,
            ),
            "upstream-name": _make_cert(
                cls.work / "upstream-name",
                "bucket-files",
                ["bucket-files", "bucket-images"],
                ca,
            ),
        }

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "nginx", None):
            _stop_nginx(cls.nginx)
        _restore_trust(getattr(cls, "trust_saved", {}))
        hosts = Path("/etc/hosts")
        if hosts.exists():
            lines = [
                line for line in hosts.read_text().splitlines(True)
                if FILES_HOST not in line and IMAGES_HOST not in line
            ]
            hosts.write_text("".join(lines))
        subprocess.run(["/usr/sbin/ip", "link", "del", "veth-gw"], check=False, capture_output=True)
        subprocess.run(["/usr/sbin/ip", "netns", "del", "bucket"], check=False, capture_output=True)

    @classmethod
    def _prepare_host(cls):
        if subprocess.run(["id", "nginx"], capture_output=True).returncode != 0:
            _run([
                "useradd", "--system", "--no-create-home",
                "--shell", "/usr/sbin/nologin", "nginx",
            ])
        for path in (
            Path("/var/log/nginx"),
            Path("/var/cache/nginx/client_temp"),
            Path("/var/cache/nginx/proxy_temp"),
            Path("/var/cache/nginx/fastcgi_temp"),
            Path("/var/cache/nginx/uwsgi_temp"),
            Path("/var/cache/nginx/scgi_temp"),
            Path("/data/ssl"),
        ):
            path.mkdir(parents=True, exist_ok=True)
        os.chmod("/var/log/nginx", 0o777)
        os.chmod("/var/cache/nginx", 0o777)
        _openssl([
            "req", "-x509", "-nodes", "-days", "2", "-newkey", "rsa:2048",
            "-keyout", "/data/ssl/nginx-gw.key", "-out", "/data/ssl/nginx-gw.crt",
            "-subj", "/CN=gateway.local",
        ])
        subprocess.run(["/usr/sbin/ip", "netns", "del", "bucket"], check=False, capture_output=True)
        subprocess.run(["/usr/sbin/ip", "link", "del", "veth-gw"], check=False, capture_output=True)
        _run(["ip", "netns", "add", "bucket"])
        _run(["ip", "link", "add", "veth-gw", "type", "veth", "peer", "name", "veth-bucket"])
        _run(["ip", "link", "set", "veth-bucket", "netns", "bucket"])
        _run(["ip", "addr", "add", f"{GATEWAY_IP}/24", "dev", "veth-gw"])
        _run(["ip", "link", "set", "veth-gw", "up"])
        _run(["ip", "netns", "exec", "bucket", "ip", "link", "set", "lo", "up"])
        _run(["ip", "netns", "exec", "bucket", "ip", "addr", "add", f"{BUCKET_IP}/24", "dev", "veth-bucket"])
        _run(["ip", "netns", "exec", "bucket", "ip", "link", "set", "veth-bucket", "up"])
        hosts = Path("/etc/hosts")
        line = f"{BUCKET_IP} {FILES_HOST} {IMAGES_HOST}\n"
        text = hosts.read_text()
        if line not in text:
            hosts.write_text(text + line)
        mime = NGINX_SRC / "conf/mime.types"
        etc = Path("/etc/nginx")
        if etc.exists():
            shutil.rmtree(etc)
        (etc / "conf.d").mkdir(parents=True)
        shutil.copy(mime, etc / "mime.types")

    def _install(self, tls_dir: Path):
        rendered = _template_files(tls_dir)
        etc = Path("/etc/nginx")
        confd = etc / "conf.d"
        if confd.exists():
            shutil.rmtree(confd)
        confd.mkdir()
        (etc / "nginx.conf").write_text(rendered["nginx_conf"])
        (confd / "include-ssl.conf").write_text(rendered["include_ssl"])
        _envsubst(rendered["templates"], confd)
        _install_trust(confd, self.ca_cert, self.trust_saved)
        _reset_cache()
        log = Path("/var/log/nginx/error.log")
        log.write_text("")
        os.chmod(log, 0o666)

    def _exchange(self, kind: str, path: str, requests: int = 1):
        cert, key = self.certs[kind]
        marker = MARKER_LEGIT if kind == "legit" else MARKER_ATTACK
        peer = BucketPeer(self.work, cert, key, marker)
        peer.start()
        try:
            _start_nginx(self.nginx)
            last = None
            for _ in range(requests):
                last = _fetch(path)
            return last
        finally:
            peer.stop()
            _stop_nginx(self.nginx)

    def _assert_rejected(self, path: str, status: str, body: str):
        self.assertNotIn(
            MARKER_ATTACK,
            body,
            f"{path} served the untrusted bucket body ({status})\n{_error_log_tail()}",
        )
        self.assertNotIn(
            "200",
            status,
            f"{path} returned the untrusted bucket response ({status})",
        )

    def _reject_each_public_path(self, tls_dir: Path, kind: str):
        self._install(tls_dir)
        failures = []
        for path in PUBLIC_PATHS:
            status, _, body = self._exchange(kind, path)
            try:
                self._assert_rejected(path, status, body)
            except AssertionError as exc:
                failures.append(str(exc))
        if failures:
            self.fail("\n".join(failures))

    def test_base_kustomization_deploys_bucket_gateway(self):
        base = yaml.safe_load(BASE_KUSTOMIZATION.read_text())
        self.assertIn("non-dynamic/tls", base.get("resources", []))
        overlay = yaml.safe_load((DEPLOYED_TLS / "kustomization.yaml").read_text())
        self.assertIn("../../gateway", overlay.get("resources", []))
        names = [item.get("name") for item in overlay.get("configMapGenerator", [])]
        for name in (
            "zhe-gw-include-location-files",
            "zhe-gw-include-location-images",
            "zhe-gw-include-location-ff-extension",
            "zhe-gw-include-upstream-bucket",
        ):
            self.assertIn(name, names)

    def test_deployed_gateway_rejects_self_signed_bucket_certificate(self):
        self._reject_each_public_path(DEPLOYED_TLS, "self-signed")

    def test_deployed_gateway_rejects_certificate_named_for_upstream_block(self):
        self._reject_each_public_path(DEPLOYED_TLS, "upstream-name")

    def test_deployed_gateway_does_not_replay_untrusted_bucket_body(self):
        self._install(DEPLOYED_TLS)
        cert, key = self.certs["self-signed"]
        peer = BucketPeer(self.work, cert, key, MARKER_ATTACK)
        peer.start()
        try:
            _start_nginx(self.nginx)
            for _ in range(4):
                _fetch(CACHE_PATH)
        finally:
            peer.stop()
        try:
            status, _, body = _fetch(CACHE_PATH)
        finally:
            _stop_nginx(self.nginx)
        self._assert_rejected(CACHE_PATH, status, body)

    def test_deployed_gateway_serves_certificate_matching_bucket_hostname(self):
        self._install(DEPLOYED_TLS)
        failures = []
        for path in PUBLIC_PATHS:
            status, _, body = self._exchange("legit", path)
            if "200" not in status or MARKER_LEGIT not in body:
                failures.append(f"{path} did not serve the trusted bucket ({status}, {body[:120]!r})")
        if failures:
            self.fail("\n".join(failures) + "\n" + _error_log_tail())

    def test_unused_tls_copy_rejects_self_signed_bucket_certificate(self):
        if not (UNUSED_TLS / "include-location-files.conf.template").exists():
            return
        self._reject_each_public_path(UNUSED_TLS, "self-signed")

    def test_unused_tls_copy_rejects_certificate_named_for_upstream_block(self):
        if not (UNUSED_TLS / "include-location-files.conf.template").exists():
            return
        self._reject_each_public_path(UNUSED_TLS, "upstream-name")

    def test_unused_tls_copy_serves_certificate_matching_bucket_hostname(self):
        if not (UNUSED_TLS / "include-location-files.conf.template").exists():
            return
        self._install(UNUSED_TLS)
        status, _, body = self._exchange("legit", "/files/issue-attachment")
        self.assertIn("200", status, _error_log_tail())
        self.assertIn(MARKER_LEGIT, body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
