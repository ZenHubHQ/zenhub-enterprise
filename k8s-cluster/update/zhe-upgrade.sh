#!/usr/bin/env bash

set -eu

# Check for namespace
if [ -z "${1:-}" ]; then

    echo "########################################"
    echo "    PLEASE PROVIDE Zenhub NAMESPACE"
    echo "   ./zhe-upgrade.sh <zhe_namespace>"
    echo "########################################"

    exit 1
fi

# Check for updating two versions at a time
read -p "Are you upgrading from two versions behind? (yes/no) : " UPGRADE_FROM_TWO_VERSIONS_BEHIND

# Validate input, only allow yes or no
case "${UPGRADE_FROM_TWO_VERSIONS_BEHIND}" in
  "yes" | "no" )
    # Continue with the script
    ;;
  * )
    echo "Only 'yes' or 'no' is supported, exiting upgrade."
    exit 1
    ;;
esac

# Check for non-zenhub registry
if [ -z "${2:-}" ]; then
    # Use Zenhub registry
    echo ""
    echo "No custom registry specified, using Zenhub's registry..."
    echo ""

    REGISTRY=us.gcr.io/zenhub-public
else
    # Use Customer registry
    echo "Please confirm the registry below is correct and contains Zenhub images tagged with the release you are upgrading to."
    echo ""
    echo "Your registry: ${2}"
    echo ""
    read -p "      Do you want to continue? (yes/no) : " answer
    if [[ "${answer}" != "yes" ]]; then
        echo "Only 'yes' is supported, exiting upgrade."
        exit 1;
    fi

    REGISTRY=$2

    # Replace occurences of Zenhub registry in data migration manifests with the custom registry
    sed -i.bak "s+us.gcr.io/zenhub-public+$REGISTRY+g" batch_v1_job_data_migration.yaml
    sed -i.bak "s+us.gcr.io/zenhub-public+$REGISTRY+g" batch_v1_job_data_migration_previous.yaml

    # Remove imagePullSecrets for Zenhub registry
    sed -i.bak "/remove-if-custom-registry/d" batch_v1_job_data_migration.yaml
    sed -i.bak "/remove-if-custom-registry/d" batch_v1_job_data_migration_previous.yaml

fi

NAMESPACE=$1

DEPLOYMENTS=(
raptor-sidekiq-worker
raptor-sidekiq-worker-default
raptor-admin
raptor-cable
raptor-webhook
kraken-webapp
toad-worker
admin-ui
toad-cron
raptor-api
toad-api
toad-websocket
devsite
pgbouncer
)

HPA=(
raptor-api
raptor-cable
raptor-webhook
toad-api
toad-websocket
)

SERVICES=(
admin-ui
cache-raptor-redis-headless
cache-raptor-redis-master
cache-toad-redis-headless
cache-toad-redis-master
kraken-webapp
nginx-gateway
raptor-admin
raptor-api
raptor-webhook
raptor-cable
toad-api
toad-websocket
)

CACHES=(
cache-raptor-redis-master
cache-toad-redis-master
)

# TODO Check running configuration is up to date with diff

echo ""
echo "###############################################"
echo "         Enabling Maintenance Mode"
echo "###############################################"

kubectl -n $NAMESPACE set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="TRUE"


echo ""
echo "###############################################"
echo "          Deleting Existing Jobs"
echo "###############################################"

kubectl -n $NAMESPACE delete job --all --ignore-not-found

echo "All Jobs Deleted"

echo ""
echo ""
echo "###############################################"
echo "                Deleting HPA"
echo "###############################################"

for h in "${HPA[@]}"
do
    kubectl -n $NAMESPACE delete hpa/$h --ignore-not-found
done

echo "All HPA deleted"

echo ""
echo ""
echo "###############################################"
echo "         Scaling Deployments to 0"
echo "###############################################"

for d in "${DEPLOYMENTS[@]}"
do
    kubectl -n $NAMESPACE scale deployments/$d --replicas=0
done

echo "All Deployments Scaled to 0"

echo ""
echo ""
echo "###############################################"
echo "         Starting Data Migration Job"
echo "###############################################"

echo "         Scaling up pgbouncer..."
kubectl -n $NAMESPACE scale deployments/pgbouncer --replicas=1

kubectl -n $NAMESPACE wait --for=condition=available deployment/pgbouncer --timeout=300s

echo "         Scaling up workers..."
kubectl -n $NAMESPACE scale deployments/raptor-sidekiq-worker --replicas=2

kubectl -n $NAMESPACE wait --for=condition=available deployment/raptor-sidekiq-worker --timeout=300s

# Run previous feature version data migration if UPGRADE_FROM_TWO_VERSIONS_BEHIND is set to yes
if [[ "${UPGRADE_FROM_TWO_VERSIONS_BEHIND}" == "yes" ]]; then
    echo "         Running previous feature version data migration..."
    kubectl -n $NAMESPACE apply -f batch_v1_job_data_migration_previous.yaml

    echo "         Waiting Previous Data Migration Job to be 'complete' (timeout 3000s)"
    kubectl -n $NAMESPACE wait --for=condition=complete job/data-migration-previous --timeout=3000s
fi

echo "         Updating data..."
kubectl -n $NAMESPACE apply -f batch_v1_job_data_migration.yaml

echo "         Waiting Data Migration Job to be 'complete' (timeout 3000s)"
kubectl -n $NAMESPACE wait --for=condition=complete job/data-migration --timeout=3000s

echo "###############################################"
echo "         Deleting Old Resources"
echo "###############################################"

echo "         Deleting Deployments"
for d in "${DEPLOYMENTS[@]}"
do
    kubectl -n $NAMESPACE delete deploy/$d --ignore-not-found
done

echo "         Deleting Caches"
for c in "${CACHES[@]}"
do
    kubectl -n $NAMESPACE delete sts/$c --ignore-not-found
done

echo "         Deleting Gateway"
kubectl -n $NAMESPACE delete deployment/nginx-gateway --ignore-not-found

echo "         Deleting Services"
for s in "${SERVICES[@]}"
do
    kubectl -n $NAMESPACE delete svc/$c --ignore-not-found
done

echo ""
echo ""
echo "###############################################"
echo "     Data Migration Completed Successfully"
echo " Please follow the remaining upgrade steps"
echo " to redeploy your application"
echo "###############################################"
