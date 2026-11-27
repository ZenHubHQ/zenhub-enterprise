#!/usr/bin/env bash
# Spec for the VM support-bundle archive.
#
# support_bundle.sh -V packs /opt/zenhub/configuration into the bundle the
# operator uploads to support. These checks fail while that archive still
# contains the secret values stored in configuration.yaml. They pass when
# those values are left out of the archive or replaced with blanks.
#
# The placeholders below are fake. They are not credentials.
#
# Run:
#   bash k8s-cluster/support-bundle/support_bundle_vm_secrets_test.sh

set -u

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SCRIPT="$REPO_ROOT/k8s-cluster/support-bundle/support_bundle.sh"

CONF_DIR=/opt/zenhub/configuration
BUNDLE_DIR=/opt/zenhub/support-bundle
LOG_ZH=/var/log/zenhub
LOG_NGINX=/var/log/nginx

# Obvious placeholders. Each one stands in for a documented configuration value.
PH_GITHUB_APP_SECRET=ZHE-TEST-PLACEHOLDER-GITHUB-APP-SECRET
PH_LICENSE_TOKEN=ZHE-TEST-PLACEHOLDER-LICENSE-TOKEN
PH_ADMIN_UI_PASS=ZHE-TEST-PLACEHOLDER-ADMIN-UI-PASS
PH_LDAP_BIND_PASSWORD=ZHE-TEST-PLACEHOLDER-LDAP-BIND-PASSWORD
PH_ENTRA_CLIENT_SECRET=ZHE-TEST-PLACEHOLDER-ENTRA-CLIENT-SECRET
PH_NOTION_CLIENT_SECRET=ZHE-TEST-PLACEHOLDER-NOTION-CLIENT-SECRET
PH_LOCKBOX_MASTER_KEY=ZHE-TEST-PLACEHOLDER-LOCKBOX-MASTER-KEY
PH_SUPPORT_ACCESS_KEY=ZHE-TEST-PLACEHOLDER-SUPPORT-ACCESS-KEY
PH_SUPPORT_SECRET_KEY=ZHE-TEST-PLACEHOLDER-SUPPORT-SECRET-KEY
PH_EXCLUDED_SECRET_ENV=ZHE-TEST-PLACEHOLDER-EXCLUDED-SECRET-ENV
PH_EXCLUDED_DB_ENV=ZHE-TEST-PLACEHOLDER-EXCLUDED-DB-ENV
PH_EXCLUDED_INTERNAL_ENV=ZHE-TEST-PLACEHOLDER-EXCLUDED-INTERNAL-ENV
PH_EXCLUDED_TLS_KEY=ZHE-TEST-PLACEHOLDER-EXCLUDED-TLS-KEY
PH_PUBLIC_HOSTNAME=github.example.test

SECRET_PLACEHOLDERS=(
  "$PH_GITHUB_APP_SECRET"
  "$PH_LICENSE_TOKEN"
  "$PH_ADMIN_UI_PASS"
  "$PH_LDAP_BIND_PASSWORD"
  "$PH_ENTRA_CLIENT_SECRET"
  "$PH_NOTION_CLIENT_SECRET"
  "$PH_LOCKBOX_MASTER_KEY"
  "$PH_SUPPORT_ACCESS_KEY"
  "$PH_SUPPORT_SECRET_KEY"
)

EXCLUDED_PLACEHOLDERS=(
  "$PH_EXCLUDED_SECRET_ENV"
  "$PH_EXCLUDED_DB_ENV"
  "$PH_EXCLUDED_INTERNAL_ENV"
  "$PH_EXCLUDED_TLS_KEY"
)

failures=0
workdir=
bundle_path=

say() {
  printf '%s\n' "$*"
}

fail() {
  say "FAIL: $*"
  failures=$((failures + 1))
}

pass() {
  say "PASS: $*"
}

need_dir() {
  local dir=$1
  if mkdir -p "$dir" 2>/dev/null; then
    return 0
  fi
  sudo mkdir -p "$dir"
  sudo chown "$(id -u):$(id -g)" "$dir"
}

cleanup() {
  if [[ -n "${bundle_path}" && -f "${bundle_path}" ]]; then
    rm -f "${bundle_path}"
  fi
  rm -rf "${workdir}"
  rm -rf "${CONF_DIR}"
  rm -f "${LOG_ZH}/zhe-support-bundle-test.log" "${LOG_NGINX}/zhe-support-bundle-test.log"
}
trap cleanup EXIT

if [[ ! -f "$SCRIPT" ]]; then
  say "FAIL: missing $SCRIPT"
  exit 1
fi

rm -rf "$CONF_DIR" 2>/dev/null || sudo rm -rf "$CONF_DIR"
need_dir "$CONF_DIR/ssl/developer-site"
need_dir "$BUNDLE_DIR"
need_dir "$LOG_ZH"
need_dir "$LOG_NGINX"

# The archived tree matches the VM layout the script hardcodes.
cat > "$CONF_DIR/configuration.yaml" <<EOF
---
zenhub_configuration:
  GITHUB_HOSTNAME: https://${PH_PUBLIC_HOSTNAME}
  GITHUB_APP_ID: zhe-test-app-id
  GITHUB_APP_SECRET: ${PH_GITHUB_APP_SECRET}
  ENTERPRISE_LICENSE_TOKEN: ${PH_LICENSE_TOKEN}
  ADMIN_UI_PASS: ${PH_ADMIN_UI_PASS}
  AUTHV2_LDAP_BIND_PASSWORD: ${PH_LDAP_BIND_PASSWORD}
  AUTHV2_ENTRA_ID_CLIENT_SECRET: ${PH_ENTRA_CLIENT_SECRET}
  NOTION_CLIENT_SECRET: ${PH_NOTION_CLIENT_SECRET}
  LOCKBOX_MASTER_KEY: ${PH_LOCKBOX_MASTER_KEY}
upload_bundle_vars:
  SUPPORT_BUNDLE_ACCESS_KEY: ${PH_SUPPORT_ACCESS_KEY}
  SUPPORT_BUNDLE_SECRET_KEY: ${PH_SUPPORT_SECRET_KEY}
EOF

printf '%s\n' "$PH_EXCLUDED_SECRET_ENV" > "$CONF_DIR/configuration.secret.env"
printf '%s\n' "$PH_EXCLUDED_DB_ENV" > "$CONF_DIR/database-credentials.env"
printf '%s\n' "$PH_EXCLUDED_INTERNAL_ENV" > "$CONF_DIR/internal.secret.env"
printf '%s\n' "$PH_EXCLUDED_TLS_KEY" > "$CONF_DIR/ssl/tls.key"
printf 'log-line\n' > "$LOG_ZH/zhe-support-bundle-test.log"
printf 'nginx-line\n' > "$LOG_NGINX/zhe-support-bundle-test.log"

# kubectl, curl, and journalctl are not part of the archive step. Stub them so
# the script still reaches its tar command without a cluster or a live GitHub.
workdir=$(mktemp -d)
cat > "$workdir/kubectl" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$workdir/curl" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$workdir/journalctl" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod 755 "$workdir/kubectl" "$workdir/curl" "$workdir/journalctl"

output_file="$workdir/script.out"
set +e
PATH="$workdir:$PATH" bash "$SCRIPT" -n zenhub -V >"$output_file" 2>"$workdir/script.err"
script_status=$?
set -e
say "support_bundle.sh exit status: $script_status"
if [[ "$script_status" -ne 0 ]]; then
  fail "support_bundle.sh -n zenhub -V exited $script_status"
  cat "$output_file" "$workdir/script.err"
fi

bundle_path=$(sed -n 's/^### Finished generating support bundle: //p' "$output_file" | tail -1)
if [[ -z "$bundle_path" ]]; then
  fail "script did not report a bundle path"
  cat "$output_file" "$workdir/script.err"
  exit 1
fi
say "bundle: $bundle_path"

case "$bundle_path" in
  /opt/zenhub/support-bundle/support_bundle_*.tar) ;;
  *) fail "VM bundle path was not under /opt/zenhub/support-bundle: $bundle_path" ;;
esac

if [[ ! -f "$bundle_path" ]]; then
  fail "bundle file was not created"
  exit 1
fi

members="$workdir/members.txt"
tar -tzf "$bundle_path" > "$members"

if grep -qx './cluster_overview.log' "$members" || grep -qx 'cluster_overview.log' "$members"; then
  pass "archive contains the script's cluster overview"
else
  fail "archive is missing cluster_overview.log, so the script tar did not run"
  cat "$members"
fi

# Secret values from configuration.yaml must not survive into the bundle,
# whether the file is stored whole or copied under another name.
extract="$workdir/extract"
mkdir -p "$extract"
tar -xzf "$bundle_path" -C "$extract"
contents="$workdir/contents.txt"
# Include member names so a secret value used as a filename is visible too.
{
  cat "$members"
  tar -xOzf "$bundle_path"
} > "$contents" 2>"$workdir/tar-extract.err" || true

for placeholder in "${SECRET_PLACEHOLDERS[@]}"; do
  if grep -q -F -- "$placeholder" "$contents"; then
    fail "bundle contains configuration secret placeholder $placeholder"
  else
    pass "bundle omits $placeholder"
  fi
done

for placeholder in "${EXCLUDED_PLACEHOLDERS[@]}"; do
  if grep -q -F -- "$placeholder" "$contents"; then
    fail "bundle contains a value the script already tries to exclude ($placeholder)"
  else
    pass "bundle omits excluded-file placeholder $placeholder"
  fi
done

# A non-secret setting may remain so support can still see the deployment.
if grep -q -F -- "$PH_PUBLIC_HOSTNAME" "$contents"; then
  pass "non-secret GitHub hostname is still available to support"
else
  pass "GitHub hostname was omitted with the secret-bearing file"
fi

if [[ "$failures" -ne 0 ]]; then
  say "members:"
  cat "$members"
  say "$failures check(s) failed"
  exit 1
fi

say "all checks passed"
exit 0
