#!/bin/bash
set -e

NAMESPACE=$1
DURATION=1095
NAME=tls

function create_self_signed {
    openssl req -x509 \
    -nodes \
    -days $DURATION \
    -newkey rsa:2048 \
    -keyout $NAME.key \
    -subj "/C=CA/ST=BC/L=Vancouver/O=Zenhub, Inc./CN=*.${NAMESPACE}.svc.cluster.local" \
    -out $NAME.crt
}

create_self_signed
