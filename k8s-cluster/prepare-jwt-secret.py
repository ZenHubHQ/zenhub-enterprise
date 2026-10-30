#!/usr/bin/env python3
"""Prepare a private JWT key file for Kustomize without changing the cluster."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys


def prepare(directory, context=None):
    configuration = (directory / 'kustomization.yaml').read_text()
    namespaces = re.findall(
        r'''^namespace:\s*(["']?)([a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?)\1\s*(?:#.*)?$''',
        configuration, re.MULTILINE,
    )
    if len(namespaces) != 1:
        raise ValueError('Set one valid top-level namespace in kustomization.yaml first')
    namespace = namespaces[0][1]
    path = directory / 'devise-jwt-secret.key'
    if path.is_symlink():
        raise ValueError('The signing-key file must not be a symbolic link')
    saved = path.read_bytes() if path.exists() else None
    if saved is not None and not saved.strip():
        raise ValueError('Existing signing-key file is empty; investigate before replacing it')

    command = ['kubectl'] + (['--context', context] if context else [])
    command += ['-n', namespace, 'get', 'secret', 'raptor', '--ignore-not-found', '-o', 'json']
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('Cannot read the Raptor Secret; check the Kubernetes context and permissions. No key was changed.')
    try:
        resource = json.loads(result.stdout) if result.stdout.strip() else {}
        live = base64.b64decode(resource.get('data', {}).get('devise_jwt_secret_key', ''), validate=True)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Cannot decode the active signing key; no key was changed') from None
    if live and not live.strip():
        raise ValueError('The active signing key contains only whitespace; investigate before replacing it')
    if saved and live and saved != live:
        raise ValueError('Local and active signing keys conflict; refusing to rotate either key')

    key = saved or live or secrets.token_hex(64).encode('ascii')
    if saved is None:
        # Exclusive creation prevents concurrent preparation from overwriting a key.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(key)
            output.flush()
            os.fsync(output.fileno())
    path.chmod(0o600)
    print('JWT signing-key file prepared; keep it private and reuse it for future upgrades.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path.cwd(), help='Directory containing kustomization.yaml')
    parser.add_argument('--context', help='Kubernetes context; defaults to the current kubectl context')
    args = parser.parse_args()
    try:
        prepare(args.directory, args.context)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
