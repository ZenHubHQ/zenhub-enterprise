"""Pool sessions opened with the shipped postgres_url must not be cleartext.

The install manifest puts that URL in every Raptor workload that reads
postgres_url, and points it at the in-cluster PgBouncer service. These tests
open that session, with the listener TLS settings the manifests actually set,
through a TCP forwarder on the pool port. They fail while the query text and
the selected row are readable and an on-path substitution is accepted. They
pass once the shipped URL verifies the pool certificate name and the captured
bytes no longer contain the query or the row.

The base raptor-db-migrate job is not covered. base/kustomization.yaml applies
base/non-dynamic/set-raptor-db-migrate-job-vars.yaml, which replaces that
job's DATABASE_URL with pgbouncer_url. That hop is not the pool URL.
base/raptor/apps_v1_deployment_raptor-api-public.yaml also references
postgres_url, but no kustomization includes it, so it is not a running workload.

A fix the tests accept sets postgres_url to sslmode=verify-full (the host stays
the pool service name) and gives the listener a certificate for that name:
CLIENT_TLS_SSLMODE=require plus CLIENT_TLS_CERT_FILE and CLIENT_TLS_KEY_FILE
on the PgBouncer deployment, and the same client_tls_sslmode, client_tls_cert_file,
and client_tls_key_file keys in options/pgbouncer/pgbouncer.ini. The test
generates those certificate files; the manifest has to name them.

Run from the repository root:

    python3 k8s-cluster/tests/test_postgres_pool_tls.py
"""

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

import psycopg2
import yaml


REPO = Path(__file__).resolve().parents[2]
CLUSTER = REPO / "k8s-cluster"
PG_BIN = Path("/usr/lib/postgresql/16/bin")

QUERY = "SELECT payload FROM shipped_issue_rows WHERE id = 1"
MARKER = "issue-row-token-marker"
TAMPERED = "issue-row-token-XXXXXX"
assert len(MARKER) == len(TAMPERED)

DB_USER = "placeholder_user"
DB_PASSWORD = "placeholder-db-password"
DB_NAME = "raptor_production"
POOL_HOST = "pgbouncer"
BACKEND_HOST = "postgres-backend"


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_port(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"nothing accepted connections on 127.0.0.1:{port}")


def _openssl(args, cwd):
    subprocess.check_call(
        ["openssl", *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _cert(directory, name, sans):
    if isinstance(sans, str):
        sans = [sans]
    san_line = ",".join(
        f"IP:{item}" if item[:1].isdigit() else f"DNS:{item}" for item in sans
    )
    cnf = directory / f"{name}.cnf"
    cnf.write_text(
        "\n".join(
            [
                "[req]",
                "distinguished_name = dn",
                "req_extensions = ext",
                "prompt = no",
                "[dn]",
                f"CN = {sans[0]}",
                "[ext]",
                f"subjectAltName = {san_line}",
                "basicConstraints = CA:FALSE",
                "keyUsage = digitalSignature,keyEncipherment",
                "extendedKeyUsage = serverAuth,clientAuth",
                "",
            ]
        )
    )
    key = directory / f"{name}.key"
    csr = directory / f"{name}.csr"
    crt = directory / f"{name}.crt"
    _openssl(
        [
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(csr),
            "-config",
            str(cnf),
        ],
        directory,
    )
    _openssl(
        [
            "x509",
            "-req",
            "-in",
            str(csr),
            "-CA",
            "ca.crt",
            "-CAkey",
            "ca.key",
            "-CAcreateserial",
            "-out",
            str(crt),
            "-days",
            "2",
            "-extfile",
            str(cnf),
            "-extensions",
            "ext",
        ],
        directory,
    )
    os.chmod(key, 0o600)
    return crt, key


class TcpTap(threading.Thread):
    """Byte-for-byte TCP forwarder. Records both directions and substitutes
    one marker. This is the pod-network position in front of the pool port.
    """

    def __init__(self, upstream_port, replace_from, replace_to):
        super().__init__(daemon=True)
        self.upstream_port = upstream_port
        self.replace_from = replace_from
        self.replace_to = replace_to
        self.to_pool = bytearray()
        self.from_pool = bytearray()
        self._stop = threading.Event()
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self.port = self._server.getsockname()[1]
        self._server.listen(16)
        self._server.settimeout(0.2)

    def run(self):
        while not self._stop.is_set():
            try:
                client, _addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._bridge, args=(client,), daemon=True
            ).start()

    def _bridge(self, client):
        upstream = socket.create_connection(("127.0.0.1", self.upstream_port))
        threads = [
            threading.Thread(
                target=self._pump,
                args=(client, upstream, self.to_pool),
                daemon=True,
            ),
            threading.Thread(
                target=self._pump,
                args=(upstream, client, self.from_pool),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        client.close()
        upstream.close()

    def _pump(self, src, dst, record):
        # Forward each read immediately. Holding a tail for a split marker
        # stalls the startup packet, which the peer answers only after the
        # whole packet arrives. The marker is a single column value and fits
        # in one read on this loopback path; a split still leaves it in the
        # recorded bytes.
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                record.extend(data)
                dst.sendall(data.replace(self.replace_from, self.replace_to))
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def close(self):
        self._stop.set()
        self._server.close()


def _load_yaml_file(path):
    text = Path(path).read_text()
    docs = []
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict):
            docs.append(doc)
    return docs


def _walk_kustomization(path, files, patches):
    data = _load_yaml_file(path)[0]
    base = Path(path).parent
    for rel in data.get("resources") or []:
        child = base / rel
        if child.is_dir():
            _walk_kustomization(child / "kustomization.yaml", files, patches)
        else:
            files.append(child)
    for rel in data.get("patchesStrategicMerge") or []:
        patches.append(base / rel)


def _containers(doc):
    spec = doc.get("spec") or {}
    template = spec.get("template") or {}
    pod = template.get("spec") or {}
    return pod.get("containers") or []


def _merge_env(base_env, patch_env):
    merged = list(base_env or [])
    index = {
        item.get("name"): pos
        for pos, item in enumerate(merged)
        if isinstance(item, dict)
    }
    for item in patch_env or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name in index:
            merged[index[name]] = item
        else:
            index[name] = len(merged)
            merged.append(item)
    return merged


def _apply_patches(docs_by_file, patches):
    by_id = {}
    for path, doc in docs_by_file:
        kind = doc.get("kind")
        name = (doc.get("metadata") or {}).get("name")
        if kind and name:
            by_id.setdefault((kind, name), []).append(doc)
    for patch_path in patches:
        for patch in _load_yaml_file(patch_path):
            kind = patch.get("kind")
            name = (patch.get("metadata") or {}).get("name")
            targets = by_id.get((kind, name), [])
            patch_containers = {
                item.get("name"): item for item in _containers(patch)
            }
            for target in targets:
                for container in _containers(target):
                    overlay = patch_containers.get(container.get("name"))
                    if not overlay or "env" not in overlay:
                        continue
                    container["env"] = _merge_env(
                        container.get("env"), overlay.get("env")
                    )


def postgres_url_consumers():
    """Workloads whose rendered env still references the postgres_url secret."""
    files = []
    patches = []
    _walk_kustomization(CLUSTER / "kustomization.yaml", files, patches)
    update = CLUSTER / "update"
    for path in sorted(update.glob("*.yaml")):
        files.append(path)
    docs = []
    for path in files:
        for doc in _load_yaml_file(path):
            docs.append((path, doc))
    _apply_patches(docs, patches)
    found = []
    for path, doc in docs:
        kind = doc.get("kind")
        meta = doc.get("metadata") or {}
        for container in _containers(doc):
            for entry in container.get("env") or []:
                ref = (entry.get("valueFrom") or {}).get("secretKeyRef") or {}
                if ref.get("key") != "postgres_url":
                    continue
                found.append(
                    {
                        "workload": f"{kind}/{meta.get('name')}",
                        "container": container.get("name"),
                        "env": entry.get("name"),
                        "file": str(path.relative_to(REPO)),
                    }
                )
    return found


def shipped_postgres_url():
    data = _load_yaml_file(CLUSTER / "kustomization.yaml")[0]
    for generator in data.get("secretGenerator") or []:
        if generator.get("name") != "configuration":
            continue
        for literal in generator.get("literals") or []:
            key, sep, value = literal.partition("=")
            if sep and key == "postgres_url":
                return value
    raise AssertionError("postgres_url literal is missing from kustomization.yaml")


def _deployment_env(path):
    for doc in _load_yaml_file(path):
        if doc.get("kind") != "Deployment":
            continue
        if (doc.get("metadata") or {}).get("name") != "pgbouncer":
            continue
        for container in _containers(doc):
            if container.get("name") == "pgbouncer":
                env = {}
                for entry in container.get("env") or []:
                    if "value" in entry:
                        env[entry["name"]] = entry["value"]
                return env
    return {}


def _ini_settings(path):
    settings = {}
    section = None
    for raw in Path(path).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "pgbouncer" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


def listener_configs():
    """Client TLS as the default deployment and the optional ini set it.

    The image entrypoint writes client_tls_sslmode only when CLIENT_TLS_SSLMODE
    is set. Absent, PgBouncer's own default is disable. The optional ini is
    mounted over that generated file when operators enable it, so its client
    TLS settings are a second listener configuration.
    """
    env = _deployment_env(
        CLUSTER / "base/pgbouncer/apps_v1_deployment_pgbouncer.yaml"
    )
    default = {
        "name": "default-deployment",
        "client_tls_sslmode": env.get("CLIENT_TLS_SSLMODE", "disable"),
        "client_cert_configured": bool(
            env.get("CLIENT_TLS_CERT_FILE") and env.get("CLIENT_TLS_KEY_FILE")
        ),
        "client_ca_configured": bool(env.get("CLIENT_TLS_CA_FILE")),
        "server_tls_sslmode": env.get("SERVER_TLS_SSLMODE", "prefer"),
        "pool_mode": env.get("POOL_MODE", "session"),
    }
    ini = _ini_settings(CLUSTER / "options/pgbouncer/pgbouncer.ini")
    optional = {
        "name": "optional-pgbouncer-ini",
        "client_tls_sslmode": ini.get("client_tls_sslmode", "disable"),
        "client_cert_configured": bool(
            ini.get("client_tls_cert_file") and ini.get("client_tls_key_file")
        ),
        "client_ca_configured": bool(ini.get("client_tls_ca_file")),
        "server_tls_sslmode": ini.get("server_tls_sslmode", "prefer"),
        "pool_mode": ini.get("pool_mode", "session"),
    }
    return [default, optional]


def _service_forwards_tcp_to_pool():
    service = None
    for doc in _load_yaml_file(CLUSTER / "base/pgbouncer/service.yaml"):
        if doc.get("kind") == "Service":
            service = doc
    deployment_port = None
    for doc in _load_yaml_file(
        CLUSTER / "base/pgbouncer/apps_v1_deployment_pgbouncer.yaml"
    ):
        if doc.get("kind") != "Deployment":
            continue
        for container in _containers(doc):
            for port in container.get("ports") or []:
                if port.get("name") == "postgresql":
                    deployment_port = port
    if not service or not deployment_port:
        return False
    ports = (service.get("spec") or {}).get("ports") or []
    selector = (service.get("spec") or {}).get("selector") or {}
    return (
        service.get("spec", {}).get("type") == "ClusterIP"
        and ports
        and ports[0].get("port") == 5432
        and ports[0].get("protocol") == "TCP"
        and ports[0].get("targetPort") == "postgresql"
        and deployment_port.get("containerPort") == 5432
        and deployment_port.get("protocol") == "TCP"
        and selector.get("app.kubernetes.io/name") == "pgbouncer"
        and selector.get("app.kubernetes.io/component") == "pgbouncer"
    )


class PoolFixture:
    def __init__(self, root, backend_port, ca_crt):
        self.root = root
        self.backend_port = backend_port
        self.ca_crt = ca_crt
        self.processes = []
        self.taps = []

    def close(self):
        for tap in self.taps:
            tap.close()
        for proc in self.processes:
            proc.terminate()
        for proc in self.processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def start_listener(self, config, certificate_name):
        crt, key = _cert(self.root, f"{config['name']}-{certificate_name}", certificate_name)
        client_mode = config["client_tls_sslmode"]
        # PgBouncer refuses client TLS unless the certificate and key are set
        # (and a CA file when it must verify client certificates). A mode name
        # with those files absent does not encrypt the listener.
        if client_mode != "disable" and not config["client_cert_configured"]:
            client_mode = "disable"
        if (
            client_mode in ("verify-ca", "verify-full")
            and not config["client_ca_configured"]
        ):
            client_mode = "disable"
        port = _free_port()
        ini = self.root / f"{config['name']}-{certificate_name}.ini"
        auth = self.root / "userlist.txt"
        auth.write_text(f'"{DB_USER}" ""\n')
        lines = [
            "[databases]",
            (
                f"{DB_NAME} = host=127.0.0.1 port={self.backend_port} "
                f"dbname={DB_NAME} user={DB_USER}"
            ),
            "[pgbouncer]",
            "listen_addr = 127.0.0.1",
            f"listen_port = {port}",
            "unix_socket_dir =",
            f"auth_file = {auth}",
            "auth_type = trust",
            f"pool_mode = {config['pool_mode']}",
            "ignore_startup_parameters = extra_float_digits",
            "server_connect_timeout = 3",
            "client_login_timeout = 5",
            f"server_tls_sslmode = {config['server_tls_sslmode']}",
            f"server_tls_ca_file = {self.ca_crt}",
            f"pidfile = {self.root / (config['name'] + certificate_name + '.pid')}",
        ]
        if client_mode != "disable":
            lines.append(f"client_tls_sslmode = {client_mode}")
            lines.append(f"client_tls_cert_file = {crt}")
            lines.append(f"client_tls_key_file = {key}")
            if client_mode in ("verify-ca", "verify-full"):
                lines.append(f"client_tls_ca_file = {self.ca_crt}")
        ini.write_text("\n".join(lines) + "\n")
        log_path = self.root / f"{config['name']}-{certificate_name}.log"
        log = open(log_path, "w")
        proc = subprocess.Popen(
            ["pgbouncer", str(ini)],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        log.close()
        self.processes.append(proc)
        try:
            _wait_port(port)
        except Exception:
            log.flush()
            raise RuntimeError(log_path.read_text()) from None
        tap = TcpTap(port, MARKER.encode(), TAMPERED.encode())
        tap.start()
        self.taps.append(tap)
        _wait_port(tap.port)
        return tap


def _dsn(product_url, port, sslrootcert=None, client_crt=None, client_key=None):
    parts = urllib.parse.urlsplit(product_url)
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    query["hostaddr"] = "127.0.0.1"
    mode = query.get("sslmode", "")
    if sslrootcert and mode.startswith("verify"):
        query["sslrootcert"] = str(sslrootcert)
    if client_crt and mode not in ("", "disable"):
        query["sslcert"] = str(client_crt)
        query["sslkey"] = str(client_key)
    netloc = f"{DB_USER}:{DB_PASSWORD}@{parts.hostname}:{port}"
    return urllib.parse.urlunsplit(
        (parts.scheme or "postgresql", netloc, parts.path, urllib.parse.urlencode(query), "")
    )


def _select(dsn):
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute(QUERY)
        row = cur.fetchone()
        return None if row is None else row[0]
    finally:
        conn.close()


class PostgresPoolTlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.consumers = postgres_url_consumers()
        if not cls.consumers:
            raise RuntimeError("no workloads reference postgres_url")
        cls.product_url = shipped_postgres_url()
        cls.listeners = listener_configs()
        cls.tmp = Path(tempfile.mkdtemp(prefix="pool-tls-"))
        _openssl(
            [
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                "ca.key",
                "-out",
                "ca.crt",
                "-days",
                "2",
                "-subj",
                "/CN=pool-test-ca",
            ],
            cls.tmp,
        )
        backend_crt, backend_key = _cert(
            cls.tmp, "backend", [BACKEND_HOST, "127.0.0.1"]
        )
        client_crt, client_key = _cert(cls.tmp, "client", "raptor-client")
        cls.client_crt = client_crt
        cls.client_key = client_key
        cls.backend_port = _free_port()
        data = cls.tmp / "pgdata"
        subprocess.check_call(
            [
                str(PG_BIN / "initdb"),
                "-D",
                str(data),
                "-A",
                "trust",
                "--username",
                DB_USER,
                "--encoding",
                "UTF8",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        conf = data / "postgresql.conf"
        with conf.open("a") as handle:
            handle.write(
                "\n".join(
                    [
                        "listen_addresses = '127.0.0.1'",
                        f"port = {cls.backend_port}",
                        "ssl = on",
                        f"ssl_cert_file = '{backend_crt}'",
                        f"ssl_key_file = '{backend_key}'",
                        "unix_socket_directories = '/tmp'",
                        "",
                    ]
                )
            )
        (data / "pg_hba.conf").write_text(
            "\n".join(
                [
                    "local all all trust",
                    "hostssl all all 127.0.0.1/32 trust",
                    "hostnossl all all 127.0.0.1/32 reject",
                    "",
                ]
            )
        )
        subprocess.check_call(
            [
                str(PG_BIN / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(cls.tmp / "postgres.log"),
                "start",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.pgdata = data
        _wait_port(cls.backend_port)
        admin = psycopg2.connect(
            f"host=/tmp port={cls.backend_port} dbname=postgres user={DB_USER}"
        )
        admin.autocommit = True
        cur = admin.cursor()
        cur.execute(f"CREATE DATABASE {DB_NAME}")
        admin.close()
        db = psycopg2.connect(
            f"host=/tmp port={cls.backend_port} dbname={DB_NAME} user={DB_USER}"
        )
        db.autocommit = True
        cur = db.cursor()
        cur.execute("CREATE TABLE shipped_issue_rows (id int PRIMARY KEY, payload text)")
        cur.execute(
            "INSERT INTO shipped_issue_rows (id, payload) VALUES (1, %s)",
            (MARKER,),
        )
        db.close()
        cls.fixture = PoolFixture(cls.tmp, cls.backend_port, cls.tmp / "ca.crt")
        cls.matching = {}
        cls.wrong = {}
        for config in cls.listeners:
            cls.matching[config["name"]] = cls.fixture.start_listener(config, POOL_HOST)
            cls.wrong[config["name"]] = cls.fixture.start_listener(
                config, "not-the-pool"
            )

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "fixture", None):
            cls.fixture.close()
        if getattr(cls, "pgdata", None):
            subprocess.call(
                [str(PG_BIN / "pg_ctl"), "-D", str(cls.pgdata), "stop", "-m", "immediate"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if getattr(cls, "tmp", None):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _dsn_for(self, port, config):
        client_crt = client_key = None
        if config["client_tls_sslmode"] in ("verify-ca", "verify-full"):
            client_crt = self.client_crt
            client_key = self.client_key
        return _dsn(
            self.product_url,
            port,
            sslrootcert=self.tmp / "ca.crt",
            client_crt=client_crt,
            client_key=client_key,
        )

    def test_service_is_the_unmodified_tcp_path_to_the_pool(self):
        self.assertTrue(
            _service_forwards_tcp_to_pool(),
            "PgBouncer service is not a TCP forward to the pool listener",
        )

    def test_shipped_sessions_hide_queries_and_reject_row_substitution(self):
        default = next(
            item for item in self.listeners if item["name"] == "default-deployment"
        )
        tap = self.matching[default["name"]]
        self.assertGreaterEqual(len(self.consumers), 1)
        for consumer in self.consumers:
            with self.subTest(consumer=consumer["workload"], env=consumer["env"]):
                before_to = len(tap.to_pool)
                before_from = len(tap.from_pool)
                got = _select(self._dsn_for(tap.port, default))
                to_pool = bytes(tap.to_pool[before_to:])
                from_pool = bytes(tap.from_pool[before_from:])
                query_visible = QUERY.encode() in to_pool
                row_visible = MARKER.encode() in from_pool or MARKER.encode() in to_pool
                substituted = got != MARKER
                if query_visible or row_visible or substituted:
                    self.fail(
                        f"{consumer['workload']} {consumer['env']} "
                        f"({consumer['file']}) sent the shipped pool URL in the "
                        f"clear: query_visible={query_visible} "
                        f"row_visible={row_visible} "
                        f"client_accepted_substituted_row={substituted}"
                    )

    def test_shipped_url_rejects_a_pool_certificate_with_the_wrong_name(self):
        default = next(
            item for item in self.listeners if item["name"] == "default-deployment"
        )
        reached = _select(self._dsn_for(self.matching[default["name"]].port, default))
        self.assertIsNotNone(reached)
        try:
            got = _select(self._dsn_for(self.wrong[default["name"]].port, default))
        except psycopg2.Error:
            return
        self.fail(
            "client accepted a pool certificate whose name is not the host "
            f"in postgres_url and read {got!r}"
        )

    def test_optional_ini_listener_hides_queries_and_rejects_substitution(self):
        optional = next(
            item for item in self.listeners if item["name"] == "optional-pgbouncer-ini"
        )
        tap = self.matching[optional["name"]]
        before_to = len(tap.to_pool)
        before_from = len(tap.from_pool)
        got = _select(self._dsn_for(tap.port, optional))
        to_pool = bytes(tap.to_pool[before_to:])
        from_pool = bytes(tap.from_pool[before_from:])
        query_visible = QUERY.encode() in to_pool
        row_visible = MARKER.encode() in from_pool or MARKER.encode() in to_pool
        substituted = got != MARKER
        if query_visible or row_visible or substituted:
            self.fail(
                "optional PgBouncer ini left the client session cleartext: "
                f"query_visible={query_visible} row_visible={row_visible} "
                f"client_accepted_substituted_row={substituted}"
            )

    def test_optional_ini_rejects_a_certificate_with_the_wrong_name(self):
        optional = next(
            item for item in self.listeners if item["name"] == "optional-pgbouncer-ini"
        )
        reached = _select(self._dsn_for(self.matching[optional["name"]].port, optional))
        self.assertIsNotNone(reached)
        try:
            got = _select(self._dsn_for(self.wrong[optional["name"]].port, optional))
        except psycopg2.Error:
            return
        self.fail(
            "optional ini listener accepted a certificate whose name is not "
            f"the host in postgres_url and returned {got!r}"
        )


if __name__ == "__main__":
    unittest.main()
