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

echo "### Creating Tar archive"

# Saves to /opt/zenhub/support-bundle/ on VM or the current directory on K8s
tar_name="support_bundle_$(date +%Y-%m-%d-T%H%M%S-%Z).tar"
if [ "$on_vm" = true ]; then
  tar_name="/opt/zenhub/support-bundle/$tar_name"
  tar -czf $tar_name -C $tempdir --exclude=/opt/zenhub/configuration/ssl --exclude=/opt/zenhub/configuration/configuration.secret.env --exclude=/opt/zenhub/configuration/database-credentials.env --exclude=/opt/zenhub/configuration/internal.secret.env . /var/log/zenhub /opt/zenhub/configuration /var/log/nginx/
else
  tar -czf $tar_name -C $tempdir .
fi

echo "### Finished generating support bundle: $tar_name"
echo "### Please send the bundle to Zenhub Enterprise Support"