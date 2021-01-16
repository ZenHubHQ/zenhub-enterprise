#!/bin/bash
# ZenHub Enterprise 3.0 Migration Script (VM->Cluster)
# Oct. 22, 2020
# Author: Dylan Martyn
set -e

MIG_DIR="/tmp/zhe3-migration-files"

# Script Functions -----------------------------

check_version(){
# Must be ZenHub Enterprise 2.44
    echo "Checking for ZHE3 migration compatibility..."
    VERSION=$(cat /data/VERSION)
    if [ $VERSION == '2.44' ]; then
        echo "You are on ZHE 2.44! This migration can continue."
    else
        echo "You are not on ZHE 2.44. Please upgrade ZenHub to 2.44 before running this script."
        exit 1
    fi
}

enable_maintenance(){
    echo "WARNING: Maintenance mode will be enabled to ensure data integrity. This will cause downtime for users. Do you wish to proceed?"
    select yn in "Yes" "No"; do
        case $yn in
            Yes ) zhe-maintenance enable; break;;
            No ) exit;;
        esac
    done
}

wait_for_queues(){
    # Wait for backend job queues to empty to avoid data loss
    echo "Waiting for backend job queues to empty to avoid data loss..."

    # Wait for Toad queues to empty
    TOAD_EMPTY=0
    NUM_EMPTY=0
    while [ $TOAD_EMPTY -eq 0 ]; do
        for q in $(rabbitmqctl list_queues | tail -10 | awk '{print $2}' | xargs); do
            if [ $q -ne 0 ]; then # Queues are not empty yet
                echo "Non-empty Toad queue found, waiting for it to empty..."
                sleep 5
                break
            else
                NUM_EMPTY=$((NUM_EMPTY + 1))
                if [ $NUM_EMPTY -eq 10 ]; then # All 10 queues are empty
                    TOAD_EMPTY=1
                    echo "Toad queues are empty!"
                fi
            fi
        done
    done

    # Wait for Raptor queue to empty
    SIDEKIQ_WORKER_CID=$(docker ps | grep raptor_sidekiq_worker | awk '{print $1'})
    SIDEKIQ_REDIS_CID=$(docker ps | grep raptor_sidekiq_redis | awk '{print $1'})
    SIDEKIQ_REDIS_IP=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $SIDEKIQ_REDIS_CID)
    REDIS_URL=redis://$SIDEKIQ_REDIS_IP:6379/0

    until [ 0 -eq $(docker exec -it -e REDIS_URL=$REDIS_URL $SIDEKIQ_WORKER_CID bundle exec sidekiqmon queues | tail -1 | awk '{print $2}') ]; do
        echo "Waiting for sidekiq queue to empty..."
        sleep 5
    done
    echo "Sidekiq queue is empty!"
}

mongo_backup(){
    echo "Backing up Mongo ... ";

    if [ -d /tmp/dump ]; then
        rm -rf /tmp/dump
        rm -f /tmp/mongo.tar.gz
    fi

    mkdir -p /tmp/migrations
    ls -1 /tmp/migrations/ | \
    sed 's/^[0]*//g' | \
    grep -o '^[0-9]*' | \
    sort -n | \
    tail -1 | \
    xargs -I XX --no-run-if-empty mongo zenhub_enterprise \
    --eval "db.getCollection('migrations').findAndModify({ \
        query: { num: XX  }, \
        upsert: true, \
        update: {  num: XX }, \
        new: true \
    });"
    mongodump --out /tmp/dump
    rm -rf /tmp/mongo.tar.gz
    cd /tmp
    mkdir -p ${MIG_DIR}
    tar -zcf ${MIG_DIR}/mongo.tar.gz dump
    rm -rf /tmp/dump
    chown admin ${MIG_DIR}/mongo.tar.gz

    rm -rf /tmp/migrations

    echo "Mongo Backup Complete!"
}

postgres_backup(){
    echo "Backing up Postgres..."

    docker exec $(docker ps -q -f name=raptor_db) pg_dump -U raptor raptor_production --format=c > "${MIG_DIR}/postgres_raptor_data.dump"

    echo "Postgres Backup completed!"
}

files_backup(){
    echo "Backing up uploaded files. This may take a while depending on the number of files"
    mkdir -p ${MIG_DIR}

    if [ -e /data/uploads ]; then
        tar --warning=no-file-changed -czvf ${MIG_DIR}/uploads.tar.gz /data/uploads/ | tee /var/log/uploads_backup.log > /dev/null
    else
        echo 'The Directory "/data/uploads" does not exist' | tee /var/log/uploads_backup.log
    fi

    echo "Uploaded files backup complete!"
}

query_mime(){
    echo "Gathering MIME type information for uploaded files and images..."
    QUERY='db.getCollection("blobs").find({},{ file_id: 1, file_mime: 1, _id: 0})'
    mongo zenhub_enterprise --eval "$QUERY" | awk '{if(NR>4)print}' | jq -s -r '.' > $MIG_DIR/file_types.json
    echo "MIME types collected!"
}

get_variables(){
    echo "Gathering required environment variables for the migration..."

    cat /etc/profile.d/zhe-env.sh | egrep "\
GITHUB_APP_ID|\
GITHUB_APP_SECRET|\
GITHUB_TOKEN_VALUE_KEY|\
GITHUB_SERVER_ADDRESS|\
ZENHUB_SERVER_ADDRESS|\
INTERNAL_AUTH_TOKEN|\
GHWEBHOOK_PASS|\
GHWEBHOOK_SECRET|\
CRYPTO_PASS|\
SECRET_KEY_BASE|\
MANIFEST_FIREFOX_ID" | egrep -v "\
ZENHUB_WEBAPP_ADDRESS|\
MANIFEST_FIREFOX_UPDATE_URL|\
FIREFOX_EXT_UPDATE_LINK_PREFIX|\
ZENHUB_WEBHOOK_ADDRESS" | sed 's/export\ //' > ${MIG_DIR}/variables.txt
}

package_bundle(){
    echo "Packaging your bundle ... "
    cd $MIG_DIR && tar --warning=no-file-changed -I "gzip -9" -cvf "${HOME}/migration-data-${TIMESTAMP}.tar.gz" .
    rm -rf ${MIG_DIR}
    chown admin: "${HOME}"/"migration-data-${TIMESTAMP}".tar.gz

    cd $HOME && echo "Package ${HOME}/migration-data-${TIMESTAMP}.tar.gz complete!"
    echo "If you are testing the ZHE2->ZHE3 migration process, you may disable maintenance mode (sudo zhe-maintenance disable) to resume service for users."
    echo "If you are doing your full production ZHE2->ZHE3 migration, keep maintenance mode enabled to protect data integrity during the migration."
    echo "You can now move ${HOME}/migration-data-${TIMESTAMP}.tar.gz to your workstation or jumpbox and prepare to upload your data."
}

# Script Execution -----------------------------

# 0. Get timestamp
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
# 1. Check for correct version
check_version
# 2. Enable Maintenance Mode
enable_maintenance
# 3. Wait for worker queue jobs to finish
wait_for_queues
# 4. Dump DBs (MongoDB and PostgreSQL)
mongo_backup
postgres_backup
# 5. Get all uploaded files
files_backup
# 6. Get MIME type of all uploaded files (this is for setting Content-Type during upload)
query_mime
# 7. Get all relevant environment variables
get_variables
# 8. Bundle everything
package_bundle
