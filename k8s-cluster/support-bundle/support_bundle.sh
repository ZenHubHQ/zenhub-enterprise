#!/bin/bash

usage() {
  echo "Usage: $0 -n <namespace> [-V] [-h]"
  echo ""
  echo "Options:"
  echo "  -n <namespace>  The namespace that Zenhub is deployed in"
  echo "  -V              Flag to indicate if the script is running on a ZHE virtual machine"
  echo "  -h              Display this help message"
  echo ""
  exit 1
}

while getopts ":n:Vh" opt; do
  case ${opt} in
    V)
      on_vm=true
      ;;
    n)
      namespace="${OPTARG}"
      ;;
    h)
      usage
      ;;
    \?)
      echo "Invalid option: -${OPTARG}" >&2
      usage
      ;;
  esac
done

if [[ -z $namespace ]]; then
  echo "### No namespace provided. Please specify a namespace with the -n flag."
  usage
fi

echo "### Generating a ZHE support bundle for namespace: $namespace"

# The bundle can hold sensitive operational data, keep it private to its owner
umask 077

# Set up a temp directory to store everything we will tar up
tempdir=$(mktemp -d)
# Always delete the temp directory when the script exits
trap 'rm -rf "$tempdir"' EXIT

info_dir="$tempdir/cluster_info"
mkdir $info_dir
logs_dir="$tempdir/zenhub_logs"
mkdir $logs_dir
overview_file="$tempdir/cluster_overview.log"

# Get detailed information about the cluster and store in a directory 
kubectl -n $namespace get all > $info_dir/kubectl_get_all.log
kubectl -n $namespace describe pods > $info_dir/kubectl_describe_pods.log
kubectl -n $namespace describe jobs > $info_dir/kubectl_describe_jobs.log
kubectl -n $namespace describe deployments > $info_dir/kubectl_describe_deployments.log
kubectl -n $namespace describe configmaps > $info_dir/kubectl_describe_configmaps.log
kubectl top pods --all-namespaces > $info_dir/kubectl_top_all_pods.log
kubectl get events --all-namespaces > $info_dir/kubectl_get_all_events.log
kubectl describe nodes >> $info_dir/kubectl_describe_nodes.log

# Gather all logs from the zenhub namespace and store them in a directory
for pod in $(kubectl get pods -o name -n $namespace)
do  
  kubectl -n $namespace logs $pod --all-containers > $logs_dir/${pod//\//_}.log
done

# High level overview of cluster version and health
echo "### High Level Overview of Cluster" > $overview_file

echo "### Zenhub Version:" >> $overview_file
kubectl -n $namespace get deployment raptor-api -o=jsonpath='{.metadata.annotations.app\.kubernetes\.io\/version}' >> $overview_file
echo "" >> $overview_file

echo "### GitHub Version:" >> $overview_file
github_hostname=$(kubectl get configmap configuration -n zenhub -o jsonpath='{.data.github_hostname}')
curl -s $github_hostname/api/v3/meta | grep "installed_version" >> $overview_file

echo "### Kubernetes Version:" >> $overview_file
kubectl version --short >> $overview_file

echo "### Node Status:" >> $overview_file
kubectl get nodes >> $overview_file

echo "### Node Resources:" >> $overview_file
kubectl top nodes >> $overview_file

echo "### Pods Not Running" >> $overview_file
kubectl get pods --all-namespaces --field-selector=status.phase!=Running | grep -v Completed >> $overview_file

# Get the journalctl logs from the VM for the current and previous boot
journalctl_dir="$tempdir/journalctl"
mkdir $journalctl_dir
journalctl -b 0 > $journalctl_dir/boot-current.log
journalctl -b -1 > $journalctl_dir/boot-previous.log

# Never archive /opt/zenhub/configuration directly, its files hold the
# deployment's secrets. Only a file listing and a copy of configuration.yaml
# that keeps the values of known non-secret settings go into the bundle.
if [ "$on_vm" = true ]; then
  config_src="/opt/zenhub/configuration"
  config_dir="$tempdir/configuration"
  mkdir $config_dir

  if [ -d "$config_src" ]; then
    find "$config_src" -printf '%M %u %g %s %TY-%Tm-%Td %TH:%TM %p\n' > $config_dir/file_listing.log 2>&1
  fi

  if [ -f "$config_src/configuration.yaml" ]; then
    if ! python3 - "$config_src/configuration.yaml" > $config_dir/configuration.redacted.yaml 2> $config_dir/redaction_error.log <<'EOF'
import sys

import yaml

REDACTED = "<redacted>"

# Key paths whose values are kept. Every other value is redacted.
ALLOWED_PATHS = {
    tuple(allowed_path.split("."))
    for allowed_path in (
        "zenhub_configuration.DOMAIN_TLD",
        "zenhub_configuration.SUBDOMAIN_SUFFIX",
        "zenhub_configuration.GITHUB_HOSTNAME",
        "zenhub_configuration.GITHUB_APP_ID",
        "zenhub_configuration.CHROME_EXTENSION_WEBSTORE_URL",
        "zenhub_configuration.CHROME_EXTENSION_ID",
        "zenhub_configuration.MANIFEST_FIREFOX_ID",
        "zenhub_configuration.GRAPHQL_OPERATION_LIMIT",
        "zenhub_configuration.GRAPHQL_RUNTIME_LIMIT",
        "zenhub_configuration.REST_API_REQUEST_LIMIT",
        "zenhub_configuration.REST_API_TIME_LIMIT",
        "zenhub_configuration.NOTION_ENABLED",
        "zenhub_configuration.NOTION_CLIENT_ID",
        "zenhub_configuration.AUTHV2_ENTRA_ID_ENABLED",
        "zenhub_configuration.AUTHV2_ENTRA_ID_CLIENT_ID",
        "zenhub_configuration.AUTHV2_ENTRA_ID_TENANT_ID",
        "zenhub_configuration.AUTHV2_LDAP_ENABLED",
        "zenhub_configuration.AUTHV2_LDAP_HOST",
        "zenhub_configuration.AUTHV2_LDAP_PORT",
        "zenhub_configuration.AUTHV2_LDAP_METHOD",
        "zenhub_configuration.AUTHV2_LDAP_BASE",
        "zenhub_configuration.AUTHV2_LDAP_BIND_DN",
        "zenhub_configuration.AUTHV2_LDAP_USER_FILTER",
        "zenhub_configuration.AUTHV2_SAML_ENABLED",
        "zenhub_configuration.AUTHV2_SAML_IDP_METADATA_URL",
        "zenhub_configuration.AUTHV2_SAML_SP_ENTITY_ID",
        "zenhub_configuration.AI_FEATURES_ENABLED",
        "ssl_self_signed",
        "k8s_cidr.cluster_cidr",
        "k8s_cidr.service_cidr",
        "ip.static",
        "ip.dhcp",
        "ip.address",
        "ip.gateway",
        "ip.dns",
        "chrony.primary",
        "chrony.secondary",
        "fail2ban.custom",
        "fail2ban.fail2ban_loglevel",
        "fail2ban.fail2ban_logtarget",
        "fail2ban.fail2ban_ignoreself",
        "fail2ban.fail2ban_ignoreips",
        "fail2ban.fail2ban_bantime",
        "fail2ban.fail2ban_findtime",
        "fail2ban.fail2ban_maxretry",
        "fail2ban.fail2ban_banaction",
    )
}


def redact(node, path):
    if isinstance(node, dict):
        return {str(key): redact(value, path + (key,)) for key, value in node.items()}
    if isinstance(node, list):
        return [REDACTED for _ in node]
    if node is None:
        return None
    if path in ALLOWED_PATHS and isinstance(node, (str, int, float, bool)):
        return node
    return REDACTED


with open(sys.argv[1], "r") as config_file:
    raw_configuration = config_file.read()

# An alias under an allowed key would copy the value of a redacted anchor
if any(isinstance(event, yaml.AliasEvent) for event in yaml.parse(raw_configuration)):
    sys.exit("configuration.yaml uses YAML aliases")

configuration = yaml.safe_load(raw_configuration)

if not isinstance(configuration, dict):
    sys.exit("configuration.yaml is not a mapping")

yaml.safe_dump(redact(configuration, ()), sys.stdout, default_flow_style=False, sort_keys=False)
EOF
    then
      rm -f $config_dir/configuration.redacted.yaml
      echo "### Could not write a redacted copy of configuration.yaml, it was left out of the bundle"
    fi
  fi
fi

echo "### Creating Tar archive"

# Saves to /opt/zenhub/support-bundle/ on VM or the current directory on K8s
tar_name="support_bundle_$(date +%Y-%m-%d-T%H%M%S-%Z).tar"
if [ "$on_vm" = true ]; then
  tar_name="/opt/zenhub/support-bundle/$tar_name"
  tar -czf $tar_name -C $tempdir . /var/log/zenhub /var/log/nginx/
else
  tar -czf $tar_name -C $tempdir .
fi

echo "### Finished generating support bundle: $tar_name"
echo "### Please send the bundle to Zenhub Enterprise Support"