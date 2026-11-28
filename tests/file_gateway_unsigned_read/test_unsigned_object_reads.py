#!/usr/bin/env python3
"""Unsigned object reads through the public file gateway.

The shipped nginx gateway is the site ingress backend. Its /files/ and
/images/ locations proxy the private buckets and clear Authorization.
The AWS bucket policy shipped with the product allows anonymous GetObject
from the S3 VPC endpoint that the module requires on the node subnet.

These tests describe the behavior after that hole is closed. They fail
while an anonymous client can still read an object body, including after
the configured download lifetime, and they fail if the gateway fetches the
object before it refuses.

Run (as a user who can sudo):

    python3 tests/file_gateway_unsigned_read/test_unsigned_object_reads.py
"""

from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import signal
import socket
import socketserver
import ssl
import subprocess
import sys
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
GATEWAY_CONFIGMAP = REPO / "k8s-cluster/base/gateway/configmaps.yaml"
TLS_DIR = REPO / "k8s-cluster/base/non-dynamic/tls"
LEGACY_TLS_DIR = REPO / "k8s-cluster/base/tls"
BUCKETS_TF = REPO / "terraform-aws-zhe-backend/buckets.tf"
TOAD_CONFIGMAP = REPO / "k8s-cluster/base/toad/configmaps.yaml"
NGINX_SRC_TAG = "release-1.31.8"
NGINX_PREFIX = Path("/tmp/nginx-root")
NGINX_BIN = NGINX_PREFIX / "sbin/nginx"

# Stands in for ${data.aws_vpc_endpoint.eks_s3.id}. The value is not a
# credential; it is the endpoint id the bucket policy condition compares.
VPCE_ID = "vpce-eks-s3"
FILES_BUCKET = "zhe-files"
IMAGES_BUCKET = "zhe-images"
BUCKET_DOMAIN = "bucket.test"
FILES_HOST = f"{FILES_BUCKET}.{BUCKET_DOMAIN}"
IMAGES_HOST = f"{IMAGES_BUCKET}.{BUCKET_DOMAIN}"
BUCKET_IP = "127.0.0.2"
PUBLIC_PORT = 8443

FILE_KEY = "issue/42/brief.pdf"
FILE_BODY = b"attachment-body-files-brief"
OTHER_FILE_KEY = "issue/7/other.pdf"
OTHER_FILE_BODY = b"attachment-body-files-other"
IMAGE_KEY = "issue/42/diagram.png"
IMAGE_BODY = b"attachment-body-images-diagram"

# Fixed-value condition keys that keep a bucket policy non-public.
# awsdocs/amazon-s3-userguide doc_source/access-control-block-public-access.md
# "The meaning of public" / "Bucket policies".
_NONPUBLIC_CONDITION_KEYS = {
    "aws:PrincipalOrgID",
    "aws:SourceIp",
    "aws:SourceArn",
    "aws:SourceVpc",
    "aws:SourceVpce",
    "aws:SourceOwner",
    "aws:SourceAccount",
    "s3:x-amz-server-side-encryption-aws-kms-key-id",
    "aws:userid",
    "s3:DataAccessPointArn",
    "s3:DataAccessPointAccount",
}


def _fixed_condition_value(value) -> bool:
    values = value if isinstance(value, list) else [value]
    for item in values:
        text = str(item)
        if "*" in text or "${" in text:
            return False
    return True


def policy_is_public(policy: dict) -> bool:
    """True when an Allow is not limited by a fixed non-public condition key."""
    for statement in policy["Statement"]:
        if statement.get("Effect") != "Allow":
            continue
        limited = False
        for _operator, keys in statement.get("Condition", {}).items():
            for key, value in keys.items():
                if key in _NONPUBLIC_CONDITION_KEYS and _fixed_condition_value(value):
                    limited = True
        if not limited:
            return True
    return False


def load_bucket_policies() -> dict:
    text = BUCKETS_TF.read_text()
    text = text.replace("${aws_s3_bucket.zhe_files.arn}", f"arn:aws:s3:::{FILES_BUCKET}")
    text = text.replace("${aws_s3_bucket.zhe_images.arn}", f"arn:aws:s3:::{IMAGES_BUCKET}")
    text = text.replace("${data.aws_vpc_endpoint.eks_s3.id}", VPCE_ID)
    policies = []
    for raw in re.findall(r"policy = <<POLICY\n(.*?)\nPOLICY", text, re.S):
        policies.append(json.loads(raw))
    by_bucket = {}
    for policy in policies:
        resources = []
        for statement in policy["Statement"]:
            resource = statement["Resource"]
            resources.extend(resource if isinstance(resource, list) else [resource])
        bucket = resources[0].split(":::")[1].split("/")[0]
        if policy_is_public(policy):
            raise RuntimeError(f"stand-in expected a non-public policy for {bucket}")
        by_bucket[bucket] = policy
    return by_bucket


POLICIES = load_bucket_policies()


def _statement_matches(statement: dict, action: str, resource: str, source_vpce) -> bool:
    principal = statement.get("Principal")
    if principal != "*":
        return False
    actions = statement.get("Action")
    actions = actions if isinstance(actions, list) else [actions]
    if action not in actions and "s3:*" not in actions:
        return False
    resources = statement.get("Resource")
    resources = resources if isinstance(resources, list) else [resources]
    resource_ok = False
    for pattern in resources:
        if pattern.endswith("/*"):
            prefix = pattern[:-1]
            if resource.startswith(prefix):
                resource_ok = True
        elif pattern == resource:
            resource_ok = True
    if not resource_ok:
        return False
    for operator, keys in statement.get("Condition", {}).items():
        if operator != "StringEquals":
            return False
        for key, expected in keys.items():
            actual = source_vpce if key == "aws:SourceVpce" else None
            expected_values = expected if isinstance(expected, list) else [expected]
            if actual not in expected_values:
                return False
    return True


def authorize(action: str, bucket: str, key: str | None, source_vpce, signed: bool) -> bool:
    """S3 authorization for one request.

    Anonymous callers skip authentication and are decided by the bucket
    policy. A caller that presented signature material is authenticated
    first; this stand-in has no signing key, so that authentication fails
    and the anonymous Allow is not used.

    Object ACLs are the private canned ACL from buckets.tf (no AllUsers
    grant). The object owner is the bucket owner, so a matching bucket
    policy Allow is sufficient and the private ACL does not add a grant.
    """
    if signed:
        return False
    policy = POLICIES[bucket]
    if key is None:
        resource = f"arn:aws:s3:::{bucket}"
    else:
        resource = f"arn:aws:s3:::{bucket}/{key}"
    allowed = False
    for statement in policy["Statement"]:
        if not _statement_matches(statement, action, resource, source_vpce):
            continue
        if statement["Effect"] == "Deny":
            return False
        if statement["Effect"] == "Allow":
            allowed = True
    return allowed


def download_lifetimes_ms() -> tuple[int, int]:
    docs = list(yaml.safe_load_all(TOAD_CONFIGMAP.read_text()))
    data = next(doc["data"] for doc in docs if doc and doc.get("metadata", {}).get("name") == "toad")
    return (
        int(data["s3_user_files_download_expiration"]),
        int(data["s3_user_images_download_expiration"]),
    )


def _envsubst(template: str) -> str:
    needed = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", template))
    present = sorted(name for name in needed if name in os.environ)
    missing = sorted(needed - set(present))
    if missing:
        raise RuntimeError(f"nginx template variables are unset: {missing}")
    fmt = " ".join(f"${{{name}}}" for name in present)
    result = subprocess.run(
        ["envsubst", fmt],
        input=template,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def _load_gateway_templates() -> tuple[str, str]:
    docs = list(yaml.safe_load_all(GATEWAY_CONFIGMAP.read_text()))
    conf = next(doc["data"] for doc in docs if doc and doc.get("metadata", {}).get("name") == "zhe-gw-conf")
    nginx_conf = next(
        doc["data"]["nginx.conf"]
        for doc in docs
        if doc and doc.get("metadata", {}).get("name") == "zhe-gw-nginx-conf"
    )
    return conf["default.conf.template"], nginx_conf


def _signed_request(headers: dict, query: str) -> bool:
    if headers.get("authorization", "").strip():
        return True
    params = urllib.parse.parse_qs(query, keep_blank_values=True)
    folded = {name.lower() for name in params}
    return bool(folded & {"x-amz-algorithm", "x-amz-signature", "signature"})


class _BucketHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        reader = self.request.makefile("rb")
        writer = self.request.makefile("wb")
        try:
            while True:
                request = _read_http_request(reader)
                if request is None:
                    break
                response, record = self.server.evaluate(request)
                with self.server.log_lock:
                    self.server.log.append(record)
                writer.write(response)
                writer.flush()
                if request["headers"].get("connection", "").lower() == "close":
                    break
        except (TimeoutError, socket.timeout, ssl.SSLError, ConnectionError, BrokenPipeError):
            return
        finally:
            try:
                writer.close()
            except Exception:
                pass


def _read_http_request(reader) -> dict | None:
    line = reader.readline()
    if not line:
        return None
    parts = line.decode("iso-8859-1").strip().split(" ")
    if len(parts) < 2:
        return None
    method, target = parts[0], parts[1]
    headers = {}
    while True:
        raw = reader.readline()
        if raw in (b"\r\n", b"\n", b""):
            break
        name, value = raw.decode("iso-8859-1").split(":", 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0") or "0")
    body = reader.read(length) if length else b""
    path, _, query = target.partition("?")
    return {
        "method": method,
        "target": target,
        "path": urllib.parse.unquote(path),
        "query": query,
        "headers": headers,
        "body": body,
    }


class BucketServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, source_vpce, context):
        super().__init__(address, _BucketHandler)
        self.source_vpce = source_vpce
        self.context = context
        self.log = []
        self.log_lock = threading.Lock()
        self.objects = {
            (FILES_BUCKET, FILE_KEY): FILE_BODY,
            (FILES_BUCKET, OTHER_FILE_KEY): OTHER_FILE_BODY,
            (IMAGES_BUCKET, IMAGE_KEY): IMAGE_BODY,
        }

    def get_request(self):
        newsocket, fromaddr = self.socket.accept()
        wrapped = self.context.wrap_socket(newsocket, server_side=True)
        return wrapped, fromaddr

    def evaluate(self, request: dict) -> tuple[bytes, dict]:
        host = request["headers"].get("host", "").split(":")[0]
        bucket = {FILES_HOST: FILES_BUCKET, IMAGES_HOST: IMAGES_BUCKET}.get(host)
        key = request["path"].lstrip("/")
        action = "s3:ListBucket" if key == "" else "s3:GetObject"
        signed = _signed_request(request["headers"], request["query"])
        allowed = False
        status = 403
        payload = b"<Error><Code>AccessDenied</Code></Error>"
        if bucket is None:
            status = 404
            payload = b"<Error><Code>NoSuchBucket</Code></Error>"
        elif request["method"] not in ("GET", "HEAD"):
            status = 403
            payload = b"<Error><Code>AccessDenied</Code></Error>"
        elif authorize(
            action,
            bucket,
            None if action == "s3:ListBucket" else key,
            self.source_vpce,
            signed,
        ):
            if action == "s3:ListBucket":
                allowed = True
                status = 200
                payload = b"<ListBucketResult></ListBucketResult>"
            elif (bucket, key) not in self.objects:
                status = 404
                payload = b"<Error><Code>NoSuchKey</Code></Error>"
            else:
                allowed = True
                status = 200
                payload = self.objects[(bucket, key)]
        if request["method"] == "HEAD":
            body = b""
        else:
            body = payload
        reason = {200: "OK", 403: "Forbidden", 404: "Not Found"}[status]
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Content-Type: application/octet-stream\r\n"
            "Connection: keep-alive\r\n"
            "\r\n"
        ).encode()
        record = {
            "source_vpce": self.source_vpce,
            "method": request["method"],
            "host": host,
            "key": key,
            "action": action,
            "signed": signed,
            "authorization": request["headers"].get("authorization", ""),
            "allowed": allowed,
            "status": status,
        }
        return header + body, record


def _certificate(path: Path, names: list[str]) -> None:
    san = ",".join(f"DNS:{name}" for name in names)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(path.with_suffix(".key")),
            "-out",
            str(path),
            "-days",
            "1",
            "-subj",
            "/CN=gateway-test",
            "-addext",
            f"subjectAltName={san}",
        ],
        check=True,
        capture_output=True,
    )


def _ssl_context(cert: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, cert.with_suffix(".key"))
    return context


def _ensure_nginx() -> None:
    if NGINX_BIN.exists():
        version = subprocess.run([str(NGINX_BIN), "-v"], capture_output=True, text=True)
        if NGINX_SRC_TAG.removeprefix("release-") in (version.stderr + version.stdout):
            return
    tarball = Path("/tmp/src/nginx.tar.gz")
    source = Path("/tmp/src/nginx-release-1.31.8")
    if not source.exists():
        tarball.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "curl",
                "-fsSL",
                "-o",
                str(tarball),
                f"https://github.com/nginx/nginx/archive/refs/tags/{NGINX_SRC_TAG}.tar.gz",
            ],
            check=True,
        )
        subprocess.run(["tar", "-C", str(tarball.parent), "-xzf", str(tarball)], check=True)
    subprocess.run(
        [
            "./auto/configure",
            f"--prefix={NGINX_PREFIX}",
            "--with-http_ssl_module",
            "--with-http_v2_module",
            "--with-http_realip_module",
            "--with-threads",
        ],
        cwd=source,
        check=True,
    )
    subprocess.run(["make", "-j", str(os.cpu_count() or 2)], cwd=source, check=True)
    subprocess.run(["make", "install"], cwd=source, check=True)


def _hosts_line() -> str:
    return f"{BUCKET_IP} {FILES_HOST} {IMAGES_HOST}"


class GatewayHarness:
    def __init__(self):
        self.servers = []
        self.threads = []
        self.nginx_proc = None

    def start(self):
        if os.geteuid() != 0:
            raise RuntimeError("the gateway harness binds port 443")
        _ensure_nginx()
        if shutil.which("id") and subprocess.run(["id", "nginx"], capture_output=True).returncode != 0:
            subprocess.run(["useradd", "--system", "--no-create-home", "nginx"], check=True)
        cert_dir = Path("/tmp/file-gateway-test-certs")
        if cert_dir.exists():
            shutil.rmtree(cert_dir)
        cert_dir.mkdir()
        bucket_cert = cert_dir / "bucket.crt"
        _certificate(bucket_cert, [FILES_HOST, IMAGES_HOST])
        Path("/data/ssl").mkdir(parents=True, exist_ok=True)
        gateway_cert = Path("/data/ssl/nginx-gw.crt")
        _certificate(gateway_cert, ["zenhub.test"])
        context = _ssl_context(bucket_cert)
        for address, source_vpce in (
            ((BUCKET_IP, 443), VPCE_ID),
            ((BUCKET_IP, PUBLIC_PORT), None),
        ):
            server = BucketServer(address, source_vpce, context)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers.append(server)
            self.threads.append(thread)
        self._render_nginx()
        error_log = Path("/var/log/nginx/error.log")
        if error_log.exists():
            error_log.write_text("")
        stale = Path("/var/run/nginx.pid")
        if stale.exists():
            try:
                os.kill(int(stale.read_text().strip()), signal.SIGQUIT)
            except ProcessLookupError:
                stale.unlink(missing_ok=True)
            deadline = time.time() + 3
            while time.time() < deadline and stale.exists():
                time.sleep(0.05)
        self.nginx_proc = subprocess.Popen(
            [
                str(NGINX_BIN),
                "-p",
                "/etc/nginx",
                "-c",
                "/etc/nginx/nginx.conf",
                "-g",
                "daemon off;",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.nginx_proc.poll() is not None:
                raise RuntimeError(self.nginx_error_log())
            try:
                with socket.create_connection(("127.0.0.1", 443), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(self.nginx_error_log() or "nginx did not accept connections")

    def _render_nginx(self):
        os.environ.update(
            {
                "WEBAPP": "127.0.0.1:9",
                "API": "127.0.0.1:9",
                "WEBHOOK": "127.0.0.1:9",
                "ACTIONCABLE": "127.0.0.1:9",
                "RAPTORAPI": "127.0.0.1:9",
                "RAPTORADMIN": "127.0.0.1:9",
                "SOCKET": "127.0.0.1:9",
                "FILES_BUCKET_NAME": FILES_BUCKET,
                "IMAGES_BUCKET_NAME": IMAGES_BUCKET,
                "BUCKET_DOMAIN": BUCKET_DOMAIN,
                "FIREFOX_EXT_S3_BUCKET_DIR": "ff-extension",
            }
        )
        default_template, nginx_conf = _load_gateway_templates()
        rendered = {
            "default.conf": _envsubst(default_template),
            "include-upstream-bucket.conf": _envsubst(
                (TLS_DIR / "include-upstream-bucket.conf.template").read_text()
            ),
            "include-location-files.conf": _envsubst(
                (TLS_DIR / "include-location-files.conf.template").read_text()
            ),
            "include-location-images.conf": _envsubst(
                (TLS_DIR / "include-location-images.conf.template").read_text()
            ),
            "include-location-ff-extension.conf": _envsubst(
                (TLS_DIR / "include-location-ff-extension.conf.template").read_text()
            ),
        }
        conf_dir = Path("/etc/nginx/conf.d")
        if conf_dir.exists():
            shutil.rmtree(conf_dir)
        conf_dir.mkdir(parents=True)
        # The shipped listener is "listen 443", which binds every address.
        # The harness keeps that port and TLS settings, and pins the address
        # to 127.0.0.1 so the bucket stand-in can bind the other loopback
        # address on 443. Location matching is unchanged.
        ssl_conf = (TLS_DIR / "include-ssl.conf").read_text().replace(
            "listen 443 ssl http2;",
            "listen 127.0.0.1:443 ssl http2;",
            1,
        )
        (conf_dir / "include-ssl.conf").write_text(ssl_conf)
        for name, contents in rendered.items():
            (conf_dir / name).write_text(contents)
        Path("/etc/nginx/nginx.conf").write_text(nginx_conf)
        mime = NGINX_PREFIX / "conf/mime.types"
        shutil.copy(mime, "/etc/nginx/mime.types")
        docs = list(yaml.safe_load_all(GATEWAY_CONFIGMAP.read_text()))
        maintenance = next(
            doc["data"]["maintenance.html"]
            for doc in docs
            if doc and doc.get("metadata", {}).get("name") == "zhe-maintenance-page"
        )
        html_root = Path("/usr/share/nginx/html")
        html_root.mkdir(parents=True, exist_ok=True)
        (html_root / "maintenance.html").write_text(maintenance)
        for directory in (
            "/etc/nginx/logs",
            "/etc/nginx/client_body_temp",
            "/etc/nginx/proxy_temp",
            "/etc/nginx/fastcgi_temp",
            "/etc/nginx/uwsgi_temp",
            "/etc/nginx/scgi_temp",
            "/var/log/nginx",
            "/tmp/files",
            "/tmp/images",
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)
        hosts = Path("/etc/hosts")
        lines = [line for line in hosts.read_text().splitlines() if FILES_HOST not in line]
        lines.append(_hosts_line())
        hosts.write_text("\n".join(lines) + "\n")
        monitor = Path("/data/zhe-monitor")
        monitor.mkdir(parents=True, exist_ok=True)
        status = monitor / "maintenance-status"
        if status.exists():
            status.unlink()

    def nginx_error_log(self) -> str:
        path = Path("/var/log/nginx/error.log")
        log = path.read_text() if path.exists() else ""
        err = ""
        if self.nginx_proc and self.nginx_proc.stderr:
            err = self.nginx_proc.stderr.read()
        return f"{err}\n{log}"[-4000:]

    def mark(self) -> int:
        with self.servers[0].log_lock:
            return len(self.servers[0].log)

    def records_since(self, mark: int) -> list[dict]:
        with self.servers[0].log_lock:
            return list(self.servers[0].log[mark:])

    def request(self, method: str, path: str, headers: dict | None = None):
        context = ssl._create_unverified_context()
        connection = http.client.HTTPSConnection("127.0.0.1", 443, context=context, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            return response.status, response.getheader("Location"), body
        finally:
            connection.close()

    def stop(self):
        if self.nginx_proc and self.nginx_proc.poll() is None:
            self.nginx_proc.terminate()
            try:
                self.nginx_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.nginx_proc.kill()
        for server in self.servers:
            server.shutdown()
            server.server_close()
        hosts = Path("/etc/hosts")
        if hosts.exists():
            lines = [line for line in hosts.read_text().splitlines() if FILES_HOST not in line]
            hosts.write_text("\n".join(lines) + "\n")


HARNESS: GatewayHarness | None = None


def gateway() -> GatewayHarness:
    if HARNESS is None:
        raise RuntimeError("harness is not running")
    return HARNESS


class UnsignedObjectReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global HARNESS
        HARNESS = GatewayHarness()
        HARNESS.start()

    @classmethod
    def tearDownClass(cls):
        if HARNESS is not None:
            HARNESS.stop()

    def setUp(self):
        status = Path("/data/zhe-monitor/maintenance-status")
        if status.exists():
            status.unlink()

    def _assert_refused(self, method: str, path: str, secret: bytes, key: str, headers=None):
        mark = gateway().mark()
        status, _location, body = gateway().request(method, path, headers)
        records = gateway().records_since(mark)
        served = [record for record in records if record["allowed"] and record["key"] == key]
        self.assertIn(
            status,
            (401, 403),
            f"{method} {path} returned {status} body={body[:120]!r} upstream={records}",
        )
        self.assertNotIn(secret, body, f"{method} {path} returned the object body")
        self.assertEqual(
            served,
            [],
            f"{method} {path} fetched the object before refusing: {served}",
        )

    def test_shipped_location_templates_match_the_unused_copy(self):
        for name in (
            "include-location-files.conf.template",
            "include-location-images.conf.template",
            "include-upstream-bucket.conf.template",
        ):
            self.assertEqual(
                (TLS_DIR / name).read_text(),
                (LEGACY_TLS_DIR / name).read_text(),
                name,
            )

    def test_evaluator_allows_anonymous_get_only_through_the_vpc_endpoint(self):
        self.assertTrue(
            authorize("s3:GetObject", FILES_BUCKET, FILE_KEY, VPCE_ID, signed=False)
        )
        self.assertFalse(
            authorize("s3:GetObject", FILES_BUCKET, FILE_KEY, None, signed=False)
        )
        self.assertFalse(
            authorize("s3:GetObject", FILES_BUCKET, FILE_KEY, VPCE_ID, signed=True)
        )
        self.assertFalse(policy_is_public(POLICIES[FILES_BUCKET]))
        self.assertFalse(policy_is_public(POLICIES[IMAGES_BUCKET]))

    def test_direct_bucket_request_without_the_vpc_endpoint_is_denied(self):
        context = ssl._create_unverified_context()
        connection = http.client.HTTPSConnection(
            BUCKET_IP, PUBLIC_PORT, context=context, timeout=5
        )
        try:
            connection.request("GET", f"/{FILE_KEY}", headers={"Host": FILES_HOST})
            response = connection.getresponse()
            body = response.read()
        finally:
            connection.close()
        self.assertEqual(response.status, 403)
        self.assertNotIn(FILE_BODY, body)

    def test_unsigned_files_read_without_a_session_is_refused(self):
        self._assert_refused("GET", f"/files/{FILE_KEY}", FILE_BODY, FILE_KEY)

    def test_unsigned_files_download_suffix_is_refused(self):
        self._assert_refused("GET", f"/files/{FILE_KEY}/download", FILE_BODY, FILE_KEY)

    def test_unsigned_files_head_is_refused(self):
        self._assert_refused("HEAD", f"/files/{FILE_KEY}", FILE_BODY, FILE_KEY)

    def test_unsigned_images_read_without_a_session_is_refused(self):
        self._assert_refused("GET", f"/images/{IMAGE_KEY}", IMAGE_BODY, IMAGE_KEY)

    def test_client_authorization_header_does_not_select_an_object(self):
        self._assert_refused(
            "GET",
            f"/files/{FILE_KEY}",
            FILE_BODY,
            FILE_KEY,
            headers={"Authorization": "Bearer placeholder-session"},
        )

    def test_client_cookie_does_not_select_an_object(self):
        self._assert_refused(
            "GET",
            f"/files/{FILE_KEY}",
            FILE_BODY,
            FILE_KEY,
            headers={"Cookie": "session=placeholder"},
        )

    def test_unsigned_query_does_not_select_an_object(self):
        self._assert_refused(
            "GET",
            f"/files/{OTHER_FILE_KEY}?unused=1",
            OTHER_FILE_BODY,
            OTHER_FILE_KEY,
        )

    def test_one_object_key_does_not_return_another_object(self):
        self._assert_refused("GET", f"/files/{FILE_KEY}", FILE_BODY, FILE_KEY)
        self._assert_refused("GET", f"/files/{OTHER_FILE_KEY}", OTHER_FILE_BODY, OTHER_FILE_KEY)
        mark = gateway().mark()
        status, _location, body = gateway().request("GET", f"/files/{FILE_KEY}")
        records = gateway().records_since(mark)
        self.assertNotIn(OTHER_FILE_BODY, body)
        self.assertNotIn(FILE_BODY, body)
        self.assertIn(status, (401, 403), records)

    def test_legacy_app_files_redirect_does_not_return_the_object(self):
        status, location, body = gateway().request("GET", f"/app/files/{FILE_KEY}")
        self.assertEqual(status, 301, body)
        self.assertIsNotNone(location)
        redirected = urllib.parse.urlparse(location)
        self._assert_refused("GET", redirected.path, FILE_BODY, FILE_KEY)

    def test_collection_urls_do_not_list_the_bucket(self):
        for path in ("/files/", "/files/?list-type=2", "/images/", "/images/?list-type=2"):
            mark = gateway().mark()
            status, _location, body = gateway().request("GET", path)
            records = gateway().records_since(mark)
            self.assertEqual(status, 403, (path, body, records))
            self.assertNotIn(b"ListBucketResult", body)
            self.assertEqual(records, [])

    def test_maintenance_file_refuses_before_the_bucket_is_read(self):
        Path("/data/zhe-monitor/maintenance-status").write_text("maintenance\n")
        try:
            mark = gateway().mark()
            status, _location, body = gateway().request("GET", f"/files/{FILE_KEY}")
            records = gateway().records_since(mark)
            self.assertEqual(status, 503, body)
            self.assertNotIn(FILE_BODY, body)
            self.assertEqual(
                [record for record in records if record["allowed"]],
                [],
                records,
            )
        finally:
            Path("/data/zhe-monitor/maintenance-status").unlink(missing_ok=True)

    def test_extension_prefix_does_not_return_an_issue_image(self):
        status, _location, body = gateway().request(
            "GET", f"/zhe-public/ff-ext-signed/{IMAGE_KEY}"
        )
        self.assertNotIn(IMAGE_BODY, body, status)

    def test_reads_stay_refused_after_the_configured_download_lifetime(self):
        files_ms, images_ms = download_lifetimes_ms()
        self.assertGreater(files_ms, 0)
        self.assertGreater(images_ms, 0)
        # Config values are 60000 and 300000. S3's signatureAge example uses
        # 600000 for ten minutes, so the same integer is a millisecond
        # duration: one minute for files and five minutes for images. The
        # gateway templates never read either value. After both durations
        # the unsigned reads must still be refused.
        time.sleep(max(files_ms, images_ms) / 1000)
        self._assert_refused("GET", f"/files/{FILE_KEY}", FILE_BODY, FILE_KEY)
        self._assert_refused("GET", f"/files/{FILE_KEY}/download", FILE_BODY, FILE_KEY)
        self._assert_refused("GET", f"/images/{IMAGE_KEY}", IMAGE_BODY, IMAGE_KEY)


if __name__ == "__main__":
    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo", "-E", sys.executable, *sys.argv])
    unittest.main(verbosity=2)
