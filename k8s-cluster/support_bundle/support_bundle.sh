#!/bin/bash

while getopts ":n:" opt; do
  case ${opt} in
    n )
      namespace="${OPTARG}"
      ;;
    \? )
      echo "Invalid option"
      exit 1
      ;;
  esac
done

if [[ -z $namespace ]]; then
  echo "### No namespace provided. Please specify a namespace with the -n flag."
  exit 1
fi

echo "### Generating a support bundle for namespace: $namespace"

# Get detailed information about the cluster and store in a directory 
mkdir cluster_info
kubectl -n $namespace get all > cluster_info/kubectl_get_all.log
kubectl -n $namespace describe pods > cluster_info/kubectl_describe_pods.log
kubectl -n $namespace describe jobs > cluster_info/kubectl_describe_jobs.log
kubectl -n $namespace describe deployment > cluster_info/kubectl_describe_deployment.log
kubectl -n $namespace describe configmap > cluster_info/kubectl_describe_configmap.log
kubectl get events --all-namespaces > cluster_info/kubectl_get_all_events.log
kubectl describe node >> cluster_info/kubectl_describe_node.log

# Gather logs from all zenhub pods and store in a directory
mkdir zenhub_logs
for pod in $(kubectl get pods --selector=app.kubernetes.io/application=zenhub -o name -n $namespace)
do  
  kubectl -n $namespace logs $pod --all-containers > zenhub_logs/${pod//\//_}.log
done

# High level overview of cluster version and health
echo "### High Level Overview of Cluster" > cluster_overview.log

echo "### Zenhub Version:" >> cluster_overview.log
kubectl -n $namespace get deployment raptor-api -o=jsonpath='{.metadata.annotations.app\.kubernetes\.io\/version}' >> cluster_overview.log
echo "" >> cluster_overview.log

echo "### Kubernetes Version:" >> cluster_overview.log
kubectl version --short >> cluster_overview.log

echo "### Node Status:" >> cluster_overview.log
kubectl get nodes >> cluster_overview.log

echo "### Node Resources:" >> cluster_overview.log
kubectl top node >> cluster_overview.log

echo "### Pods Not Running" >> cluster_overview.log
kubectl get pods --all-namespaces --field-selector=status.phase!=Running | grep -v Completed >> cluster_overview.log

echo "### Creating Tar archive"

tar_name="support_bundle_$(date +%Y-%m-%d-T%H%M%S-%Z).tar"
tar -czf $tar_name \
  cluster_info \
  zenhub_logs \
  cluster_overview.log \

rm -r cluster_info
rm -r zenhub_logs
rm cluster_overview.log

echo "$tar_name"

echo "### Finished, please send your TAR to Zenhub Enterprise Support"
