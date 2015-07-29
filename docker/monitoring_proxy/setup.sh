#!/bin/bash

PROJECT_DEV="chrome-infra-mon-proxy-dev"
PROJECT_PROD="chrome-infra-mon-proxy"
MANIFEST_DEV="monitoring_proxy_containers_dev.yaml"
MANIFEST_PROD="monitoring_proxy_containers_prod.yaml"
REGION="us-central1"
INSTANCE_TYPE="n1-standard-1"
SCOPES="cloud-platform,storage-ro,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/pubsub"

function print_usage {
    echo
    echo "Usage:"
    echo "$0 <command> dev|prod"
    echo "where <command> is:"
    echo "  proxy1, proxy2 or proxy3 - respin the corresponding proxy VM."
}

_run_check() {
  $*
  RV=$?
  if [ ${RV} != 0 ]; then
    echo "ERROR: [$*] returned with non-zero ${RV}"
    exit 1
  fi
}

function delete_instance {
    # delete_instance instance-name zone-name
    local INSTANCE_NAME=$1
    local ZONE=$2
    echo "Deleting $INSTANCE_NAME"
    # Not under _run_check, because if there is no VM, the command
    # will (correctly) fail, but we should proceed creating a new VM.
    gcloud compute -q --project "$PROJECT" instances delete "$INSTANCE_NAME" \
        --zone "$ZONE"
    if [ $? != 0 ]; then
        echo "gcloud: VM failed to delete, assuming it doesn't exist."
    fi
}

function create_instance {
    # create_instance instance-name zone-name ip-name
    local INSTANCE_NAME=$1
    local ZONE=$2
    local ADDRESS=$3
    echo "Creating $INSTANCE_NAME"
    _run_check gcloud compute -q instances create "$INSTANCE_NAME" \
         --project "$PROJECT" --zone "$ZONE" --machine-type "$INSTANCE_TYPE" \
        --image container-vm --network default --address "$ADDRESS" \
        --metadata-from-file google-container-manifest="$MANIFEST" \
        --scopes "$SCOPES"
}

function respin_proxy1 {
    delete_instance proxy-go1 "$REGION-a"
    create_instance proxy-go1 "$REGION-a" proxy1
}

function respin_proxy2 {
    delete_instance proxy-go2 "$REGION-b"
    create_instance proxy-go2 "$REGION-b" proxy2
}

function respin_proxy3 {
    delete_instance proxy-go3 "$REGION-c"
    create_instance proxy-go3 "$REGION-c" proxy3
}

case $2 in
    prod)
        PROJECT="$PROJECT_PROD"
        MANIFEST="$MANIFEST_PROD"
        ;;
    dev)
        PROJECT="$PROJECT_DEV"
        MANIFEST="$MANIFEST_DEV"
        ;;
    *)
        echo "Please specify dev or prod (deployment target)."
        print_usage
        exit 1
esac

case $1 in
    proxy1)
	respin_proxy1
	;;
    proxy2)
	respin_proxy2
	;;
    proxy3)
	respin_proxy3
	;;
    *)
	echo "Unknown command: $1."
        print_usage
        exit 1
        ;;
esac
