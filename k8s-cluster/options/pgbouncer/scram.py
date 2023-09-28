#!/usr/bin/python3
import hmac
import sys
from base64 import standard_b64encode
from hashlib import pbkdf2_hmac, sha256
from os import urandom

salt_size = 16
digest_len = 32
iterations = 4096


def b64enc(b: bytes) -> str:
    return standard_b64encode(b).decode("utf8")


def pg_scram_sha256(passwd: str) -> str:
    salt = urandom(salt_size)
    digest_key = pbkdf2_hmac(
        "sha256", passwd.encode("utf8"), salt, iterations, digest_len
    )
    client_key = hmac.digest(digest_key, "Client Key".encode("utf8"), "sha256")
    stored_key = sha256(client_key).digest()
    server_key = hmac.digest(digest_key, "Server Key".encode("utf8"), "sha256")
    return (
        f"SCRAM-SHA-256${iterations}:{b64enc(salt)}"
        f"${b64enc(stored_key)}:{b64enc(server_key)}"
    )


def print_usage():
    print("Usage: provide single password argument to encrypt")
    sys.exit(1)


def main():
    args = sys.argv[1:]

    if args and len(args) > 1:
        print_usage()

    if args:
        passwd = args[0]
    else:
        passwd = sys.stdin.read().strip()

    if not passwd:
        print_usage()

    print(pg_scram_sha256(passwd))


if __name__ == "__main__":
    main()
