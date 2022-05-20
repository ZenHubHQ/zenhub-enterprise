#!/usr/bin/env bash

set -eu

# Check for namespace
if [ -z "${1:-}" ]; then

    echo "########################################"
    echo "    PLEASE PROVIDE ZenHub NAMESPACE"
    echo "   ./zhe-upgrade.sh <zhe_namespace>"
    echo "########################################"

    exit 1
fi

# Check for non-zenhub registry
if [ -z "${2:-}" ]; then
    # Use ZenHub registry
    echo ""
    echo "No custom registry specified, using ZenHub's registry..."
    echo ""

    REGISTRY=us.gcr.io/zenhub-public
else
    # Use Customer registry
    echo "Please confirm the registry below is correct and contains ZenHub images tagged with the release you are upgrading to."
    echo ""
    echo "Your registry: ${2}"
    echo ""
    read -p "      Do you want to continue? (yes/no) : " answer
    if [[ "${answer}" != "yes" ]]; then
        echo "Only 'yes' is supported, exiting upgrade."
        exit 1;
    fi

    REGISTRY=$2

    # Replace occurences of ZenHub registry in releasereport migration manifests with the custom registry
    sed -i.bak "s+us.gcr.io/zenhub-public+$REGISTRY+g" batch_v1_job_raptor-db-migrate.yaml
    sed -i.bak "s+us.gcr.io/zenhub-public+$REGISTRY+g" batch_v1_job_releasereport_migration.yaml
    sed -i.bak "s+us.gcr.io/zenhub-public+$REGISTRY+g" apps_v1_deployment_raptor-sidekiq-worker-for-toad-events.yaml

    # Remove imagePullSecrets for ZenHub registry
    sed -i.bak "/remove-if-custom-registry/d" batch_v1_job_raptor-db-migrate.yaml
    sed -i.bak "/remove-if-custom-registry/d" batch_v1_job_releasereport_migration.yaml
    sed -i.bak "/remove-if-custom-registry/d" apps_v1_deployment_raptor-sidekiq-worker-for-toad-events.yaml

fi

IMAGE=raptor-backend
TAG=zhe-3.3.3
NAMESPACE=$1
REPLICAS=0

DEPLOYMENTS=(
raptor-sidekiq-worker
raptor-admin
raptor-cable
kraken-webapp
toad-worker
toad-webhook
admin-ui
toad-cron
raptor-api
toad-api
toad-websocket
)

HPA=(
raptor-api
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
raptor-cable
toad-api
toad-webhook
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
    kubectl -n $NAMESPACE scale deployments/$d --replicas=$REPLICAS
done

echo "All Deployments Scaled to 0"

echo ""
echo ""
echo "###############################################"
echo "         Starting Release Report Migration Job"
echo "###############################################"

echo "         Updating Databases..."
kubectl -n $NAMESPACE apply -f batch_v1_job_raptor-db-migrate.yaml

echo "         Waiting DB Migration Job to be 'complete' (timeout 3000s)"
kubectl -n $NAMESPACE wait --for=condition=complete job/db-migration --timeout=3000s

echo "         Updating raptor-sidekiq-worker..."
kubectl -n $NAMESPACE set image deployment/raptor-sidekiq-worker \
    raptor-sidekiq-worker=$REGISTRY/$IMAGE:$TAG
kubectl -n $NAMESPACE scale deployments/raptor-sidekiq-worker --replicas=2
# kubectl -n $NAMESPACE rollout restart deployment/raptor-sidekiq-worker
kubectl -n $NAMESPACE wait --for=condition=available deployment/raptor-sidekiq-worker --timeout=300s

# Required for upgrades with migrations that use the toad_events_processor queue
kubectl -n $NAMESPACE apply -f apps_v1_deployment_raptor-sidekiq-worker-for-toad-events.yaml

# Required just for 3.2 -> 3.3 upgrade due to new hubspot_api_key key
# being required by the raptor-backend:3.3.3 image to run the
# releasereport-migration pod
echo "         Adding required secret..."
kubectl -n $NAMESPACE apply -f ../base/raptor/secret.yaml

echo "         Updating data..."
kubectl -n $NAMESPACE apply -f batch_v1_job_releasereport_migration.yaml

echo "         Waiting Release Report Migration Job to be 'complete' (timeout 3000s)"
kubectl -n $NAMESPACE wait --for=condition=complete job/releasereport-migration --timeout=3000s

# Wait for toad_events_processor sidekiq queue to empty, required only for toad migrations that use that queue
SIDEKIQ_WORKER_POD_NAME=$(kubectl -n $NAMESPACE get pods --selector=app.kubernetes.io/component=raptor-sidekiq-worker-for-toad-events -o jsonpath='{.items[0]..metadata.name}')
TOAD_QUEUE_SIZE="1"
while [ $TOAD_QUEUE_SIZE != 0 ]
do
  RAILS_QUERY_OUTPUT=$(kubectl -n $NAMESPACE exec $SIDEKIQ_WORKER_POD_NAME -- /bin/sh -c "echo 'Sidekiq::Queue.new(\"toad_events_processor\").size' | rails c" 2> /dev/null)
  TOAD_QUEUE_SIZE=$(echo $RAILS_QUERY_OUTPUT | tail -n1)
  echo "Events in queue remaining: $TOAD_QUEUE_SIZE"
  sleep 30
done

# Required for upgrades with migrations that use the toad_events_processor queue
kubectl -n $NAMESPACE delete -f apps_v1_deployment_raptor-sidekiq-worker-for-toad-events.yaml

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
kubectl -n $NAMESPACE delete deployment/nginx-gateway

echo "         Deleting Services"
for s in "${SERVICES[@]}"
do
    kubectl -n $NAMESPACE delete svc/$c --ignore-not-found
done

echo ""
echo ""
echo "###############################################"
echo "         Migration Completed Successfully"
echo " Please update your kustomization.yaml"
echo " with the new image tags and redeploy"
echo "###############################################"
