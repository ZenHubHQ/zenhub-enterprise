#!/usr/bin/env python3
"""Failing spec for unauthenticated ElastiCache access.

These tests exercise the backend module as an operator would use it with the
Raptor manifests: the published Redis URL is the connection string, the
security-group and network-ACL rules decide who in the VPC can open the port,
and a Redis process is started with the authentication and TLS those resources
actually configure.

They must fail while the cache accepts commands from a VPC peer that was not
given a credential. They pass once that peer cannot read the GraphQL cache
database, inject an ActionCable broadcast, or have a Sidekiq worker perform a
forged job.

Not covered, because they are separate stores or do not stop this peer:
the in-cluster cache-raptor-redis StatefulSet (it sets requirepass), and
encryption at rest (it does not gate Redis commands).

Run from the repository root:

    python3 -m pip install python-hcl2
    # Redis 7.x CLI and server, Ruby, and Sidekiq 7.3.1 (the processor under test)
    gem install --user-install sidekiq -v 7.3.1
    python3 terraform-aws-zhe-backend/tests/test_unauthenticated_elasticache_access.py
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import hcl2

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "terraform-aws-zhe-backend"
KUSTOMIZATION = REPO / "k8s-cluster" / "kustomization.yaml"
SIDEKIQ_DEPLOYMENT = (
    REPO
    / "k8s-cluster"
    / "base"
    / "raptor"
    / "apps_v1_deployment_raptor-sidekiq-worker.yaml"
)
WORKER = Path(__file__).resolve().parent / "sidekiq_probe_worker.rb"

# A host inside the VPC that is not the Raptor process. The security group
# expression data.aws_vpc.zhe.cidr_block is the whole VPC, so this address is
# one of the peers that rule admits.
VPC_CIDR = ipaddress.ip_network("10.0.0.0/16")
ATTACKER_IP = ipaddress.ip_address("10.0.1.20")

GRAPHQL_KEY = "graphql:cache:probe"
GRAPHQL_VALUE = "workspace-record"
CABLE_CHANNEL = "zhe_action_cable_probe"
CABLE_PAYLOAD = "injected-broadcast"
JOB_ARGUMENT = "attacker-chosen-argument"


def unquote(value):
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def load_module():
    merged = {"resource": [], "output": [], "variable": []}
    for path in sorted(MODULE.glob("*.tf")):
        with path.open() as handle:
            parsed = hcl2.load(handle)
        for kind in merged:
            merged[kind].extend(parsed.get(kind, []))
    return merged


def variable_defaults(module):
    defaults = {}
    for block in module["variable"]:
        for raw_name, body in block.items():
            name = unquote(raw_name)
            if "default" in body:
                defaults[name] = unquote(body["default"])
    return defaults


def iter_resources(module):
    for block in module["resource"]:
        for raw_type, resources in block.items():
            type_name = unquote(raw_type)
            for raw_name, body in resources.items():
                yield type_name, unquote(raw_name), body


def created_by_default(body, defaults):
    """True when the resource exists under the module's default variables."""
    count = body.get("count")
    if count is None:
        return True
    text = str(unquote(count)).replace(" ", "")
    if text in {"0", "false"}:
        return False
    if "var.create_redis?1:0" in text or text == "${var.create_redis?1:0}":
        return bool(defaults.get("create_redis", True))
    if text.startswith("${var.create_redis"):
        return bool(defaults.get("create_redis", True))
    return True


def truthy(value):
    value = unquote(value)
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text not in {"", "false", "null", "0", "[]", "${null}"}


def output_block(module, name):
    for block in module["output"]:
        for raw_name, body in block.items():
            if unquote(raw_name) == name:
                return body
    raise KeyError(name)


def redis_resources(module, defaults):
    found = []
    for type_name, name, body in iter_resources(module):
        if type_name not in {
            "aws_elasticache_cluster",
            "aws_elasticache_replication_group",
            "aws_elasticache_serverless_cache",
        }:
            continue
        if not created_by_default(body, defaults):
            continue
        engine = unquote(body.get("engine", "redis"))
        if engine not in {"redis", "valkey"} and type_name != "aws_elasticache_serverless_cache":
            continue
        found.append((type_name, name, body))
    return found


def resource_requires_auth(body):
    for key in ("auth_token", "auth_token_wo", "user_group_ids", "user_group_id"):
        if key in body and truthy(body.get(key)):
            return True
    return False


def resource_requires_tls(body):
    return truthy(body.get("transit_encryption_enabled"))


def cidr_admits_attacker(entry):
    text = str(unquote(entry)).strip()
    if "data.aws_vpc.zhe.cidr_block" in text:
        return True
    if text in {"0.0.0.0/0", "::/0"}:
        return True
    if text.startswith("${") or text.startswith("data.") or text.startswith("var."):
        return False
    try:
        network = ipaddress.ip_network(text, strict=False)
    except ValueError:
        return False
    return ATTACKER_IP in network


def rule_admits_attacker(body):
    """A rule admits the VPC peer when an ingress allow lists the VPC CIDR.

    source_security_group_id alone does not. This peer is a different workload
    and is not a member of that group.
    """
    if unquote(body.get("type", "ingress")) not in {"ingress", None}:
        return False
    if "egress" in body and body.get("egress") is True:
        return False
    if unquote(body.get("rule_action", "allow")) not in {"allow", None}:
        return False
    protocol = unquote(body.get("protocol", "tcp"))
    if protocol not in {"tcp", "6", "-1"}:
        return False
    cidrs = list(body.get("cidr_blocks") or [])
    cidrs += list(body.get("ipv6_cidr_blocks") or [])
    cidrs += list(body.get("cidr_block") or [])
    if isinstance(body.get("cidr_block"), str):
        cidrs.append(body.get("cidr_block"))
    return any(cidr_admits_attacker(item) for item in cidrs)


def rule_targets_redis_port(body, defaults):
    redis_port = int(defaults.get("redis_port", 6379))
    for key in ("from_port", "to_port"):
        if key not in body:
            continue
        value = unquote(body[key])
        if isinstance(value, int) and value not in {redis_port, 0}:
            return False
        text = str(value)
        if text.startswith("${") and "redis_port" not in text and text not in {"0"}:
            if not text.endswith(str(redis_port)):
                return False
    return True


def network_allows_attacker(module, defaults):
    """Both the security group and the network ACL must allow the peer."""
    sg_allow = False
    nacl_allow = False
    for type_name, _name, body in iter_resources(module):
        if not created_by_default(body, defaults):
            continue
        if not rule_targets_redis_port(body, defaults):
            continue
        if not rule_admits_attacker(body):
            continue
        if type_name == "aws_security_group_rule":
            sg_allow = True
        elif type_name == "aws_network_acl_rule":
            nacl_allow = True
    return sg_allow and nacl_allow


def published_url_expression(module):
    body = output_block(module, "zhe_redis_endpoint")
    return str(unquote(body.get("value", ""))), bool(body.get("sensitive"))


def database_indexes():
    """Database numbers from the kustomization the operator fills in."""
    text = KUSTOMIZATION.read_text()
    found = {}
    for name in ("redis_url", "cable_redis_url", "graphql_redis_url"):
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"- {name}=") or stripped.startswith(f"{name}="):
                path = stripped.split("=", 1)[1].rstrip("/").rsplit("/", 1)[-1]
                found[name] = int(path)
    return found


class RedisProcess:
    def __init__(self, port, require_password, tls_dir):
        self.port = port
        self.require_password = require_password
        self.tls_dir = tls_dir
        self.process = None
        self.placeholder = None

    def start(self):
        if self.require_password:
            # Runtime stand-in for a generated auth token. Not a product secret.
            self.placeholder = "placeholder-auth-token"
        cmd = [
            "redis-server",
            "--bind",
            "127.0.0.1",
            "--protected-mode",
            "no",
            "--maxmemory-policy",
            "noeviction",
            "--save",
            "",
            "--appendonly",
            "no",
            "--daemonize",
            "no",
            "--logfile",
            "",
        ]
        if self.tls_dir:
            cert = self.tls_dir / "redis.crt"
            key = self.tls_dir / "redis.key"
            write_cert(cert, key)
            cmd += [
                "--port",
                "0",
                "--tls-port",
                str(self.port),
                "--tls-cert-file",
                str(cert),
                "--tls-key-file",
                str(key),
                "--tls-auth-clients",
                "no",
            ]
        else:
            cmd += ["--port", str(self.port)]
        if self.placeholder:
            cmd += ["--requirepass", self.placeholder]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.time() + 5
        last = ""
        while time.time() < deadline:
            if self.process.poll() is not None:
                last = self.process.stdout.read()
                raise RuntimeError(f"redis-server exited: {last}")
            try:
                reply = redis_command(self.client_args(authenticated=bool(self.placeholder)), "PING")
            except Exception as exc:
                last = str(exc)
                time.sleep(0.05)
                continue
            if reply.strip() == "PONG":
                return
            last = reply
            time.sleep(0.05)
        raise RuntimeError(f"redis-server did not accept the published client: {last}")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def client_args(self, authenticated):
        args = ["redis-cli", "-h", "127.0.0.1", "-p", str(self.port)]
        if self.tls_dir:
            args += ["--tls", "--cacert", str(self.tls_dir / "redis.crt")]
        if authenticated and self.placeholder:
            args += ["--no-auth-warning", "-a", self.placeholder]
        return args


def write_cert(cert_path, key_path):
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def redis_command(base_args, *command, database=None):
    args = list(base_args)
    if database is not None:
        args += ["-n", str(database)]
    args += list(command)
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return (completed.stdout or "") + (completed.stderr or "")


def sidekiq_bin():
    user_dir = subprocess.check_output(
        ["ruby", "-e", "print Gem.user_dir"],
        text=True,
    ).strip()
    path = Path(user_dir) / "bin" / "sidekiq"
    if not path.exists():
        raise RuntimeError(
            "sidekiq 7.3.1 is not installed. Run: gem install --user-install sidekiq -v 7.3.1"
        )
    return path


class ElastiCacheAccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.defaults = variable_defaults(cls.module)
        cls.caches = redis_resources(cls.module, cls.defaults)
        cls.url_expression, cls.url_sensitive = published_url_expression(cls.module)
        cls.databases = database_indexes()
        cls.network_open = network_allows_attacker(cls.module, cls.defaults)
        cls.auth_required = bool(cls.caches) and all(
            resource_requires_auth(body) for _type, _name, body in cls.caches
        )
        cls.tls_required = bool(cls.caches) and all(
            resource_requires_tls(body) for _type, _name, body in cls.caches
        )

    def test_deployment_points_sidekiq_at_the_published_url(self):
        text = SIDEKIQ_DEPLOYMENT.read_text()
        self.assertIn("SIDEKIQ_REDIS_URL", text)
        self.assertIn("key: redis_url", text)
        self.assertEqual(self.databases["redis_url"], 0)
        self.assertEqual(self.databases["cable_redis_url"], 1)
        self.assertEqual(self.databases["graphql_redis_url"], 2)

    def test_vpc_peer_cannot_use_the_cache(self):
        self.assertTrue(
            ATTACKER_IP in VPC_CIDR,
            "the peer used by this test must sit inside the VPC CIDR",
        )
        if not self.caches:
            self.fail("default variables do not create the ElastiCache Redis the module documents")

        url_is_rediss = "rediss://" in self.url_expression and "redis://" not in self.url_expression.replace(
            "rediss://", ""
        )
        url_has_credential = "@" in self.url_expression.split("?", 1)[0]

        with tempfile.TemporaryDirectory(prefix="elasticache-spec-") as tmp:
            tmp_path = Path(tmp)
            tls_dir = tmp_path / "tls" if self.tls_required else None
            if tls_dir:
                tls_dir.mkdir()
            server = RedisProcess(free_port(), self.auth_required, tls_dir)
            marker = tmp_path / "job-performed"
            sidekiq = None
            subscriber = None
            try:
                server.start()
                app = server.client_args(authenticated=True)
                # The application connects with the published URL. Ping must
                # succeed so a later "attacker failed" result is not a down server.
                self.assertEqual(
                    redis_command(app, "PING").strip(),
                    "PONG",
                    "the client using the published endpoint could not talk to Redis",
                )
                redis_command(
                    app,
                    "SET",
                    GRAPHQL_KEY,
                    GRAPHQL_VALUE,
                    database=self.databases["graphql_redis_url"],
                )

                attacker_read = False
                attacker_broadcast = False
                attacker_job = False
                if self.network_open:
                    attacker = server.client_args(authenticated=False)
                    read_reply = redis_command(
                        attacker,
                        "GET",
                        GRAPHQL_KEY,
                        database=self.databases["graphql_redis_url"],
                    )
                    attacker_read = GRAPHQL_VALUE in read_reply

                    subscriber = subprocess.Popen(
                        attacker
                        + [
                            "-n",
                            str(self.databases["cable_redis_url"]),
                            "SUBSCRIBE",
                            CABLE_CHANNEL,
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    time.sleep(0.4)
                    redis_command(
                        attacker,
                        "PUBLISH",
                        CABLE_CHANNEL,
                        CABLE_PAYLOAD,
                        database=self.databases["cable_redis_url"],
                    )
                    time.sleep(0.4)
                    subscriber.terminate()
                    cable_out, _ = subscriber.communicate(timeout=3)
                    attacker_broadcast = CABLE_PAYLOAD in (cable_out or "")

                    payload = {
                        "class": "ZheProbeJob",
                        "args": [str(marker), JOB_ARGUMENT],
                        "queue": "default",
                        "jid": "forgedjobid0001",
                        "retry": False,
                        "created_at": 1,
                        "enqueued_at": 1,
                    }
                    push_reply = redis_command(
                        attacker,
                        "LPUSH",
                        "queue:default",
                        json.dumps(payload),
                        database=self.databases["redis_url"],
                    )
                    redis_command(
                        attacker,
                        "SADD",
                        "queues",
                        "default",
                        database=self.databases["redis_url"],
                    )
                    if "NOAUTH" not in push_reply and "ERR" not in push_reply:
                        env = os.environ.copy()
                        env["REDIS_PROVIDER"] = "SIDEKIQ_REDIS_URL"
                        env["SIDEKIQ_REDIS_URL"] = published_runtime_url(server)
                        sidekiq = subprocess.Popen(
                            [
                                str(sidekiq_bin()),
                                "-r",
                                str(WORKER),
                                "-c",
                                "1",
                            ],
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                        )
                        deadline = time.time() + 20
                        while time.time() < deadline and not marker.exists():
                            if sidekiq.poll() is not None:
                                break
                            time.sleep(0.2)
                        attacker_job = marker.exists() and JOB_ARGUMENT in marker.read_text()

                with self.subTest("graphql cache read"):
                    self.assertFalse(
                        attacker_read,
                        "VPC peer read the GraphQL cache key without a credential",
                    )
                with self.subTest("action cable publish"):
                    self.assertFalse(
                        attacker_broadcast,
                        "VPC peer injected a pub/sub payload a cable subscriber received",
                    )
                with self.subTest("sidekiq perform"):
                    self.assertFalse(
                        attacker_job,
                        "Sidekiq performed a job the VPC peer LPUSHed onto queue:default",
                    )
            finally:
                if subscriber and subscriber.poll() is None:
                    subscriber.kill()
                if sidekiq and sidekiq.poll() is None:
                    sidekiq.terminate()
                    try:
                        sidekiq.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        sidekiq.kill()
                server.stop()

        with self.subTest("security group and network acl"):
            self.assertFalse(
                self.network_open,
                "Redis ingress still admits every address in the VPC CIDR",
            )
        with self.subTest("auth token"):
            self.assertTrue(
                self.auth_required,
                "ElastiCache Redis is created without an auth token or user group",
            )
        with self.subTest("transit encryption"):
            self.assertTrue(
                self.tls_required,
                "ElastiCache Redis is created without transit encryption",
            )
        with self.subTest("published url"):
            self.assertTrue(self.url_sensitive)
            self.assertTrue(
                url_is_rediss and url_has_credential,
                f"zhe_redis_endpoint is not a rediss URL with a credential: {self.url_expression}",
            )


def published_runtime_url(server: RedisProcess) -> str:
    scheme = "rediss" if server.tls_dir else "redis"
    auth = ""
    if server.placeholder:
        auth = f":{server.placeholder}@"
    return f"{scheme}://{auth}127.0.0.1:{server.port}/0"


if __name__ == "__main__":
    unittest.main(verbosity=2)
