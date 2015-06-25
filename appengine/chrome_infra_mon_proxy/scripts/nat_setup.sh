#!/bin/bash
# Run this script from its directory, to correctly pick up nat_startup.sh:
# cd scripts
# ./nat_setup.sh <command> dev|prod

PROJECT_DEV="chrome-infra-mon-proxy-dev"
PROJECT_PROD="chrome-infra-mon-proxy"
REGION="us-central1"
INSTANCE_TYPE="n1-standard-2"
GAE_VM1_TAG="managed-gae-vm1"
GAE_VM2_TAG="managed-gae-vm2"
GAE_VM3_TAG="managed-gae-vm3"

function print_usage {
    echo
    echo "Usage:"
    echo "$0 <command> dev|prod"
    echo "where <command> is one of:"
    echo "  nat1|nat2|nat3 - respin the corresponding NAT box"
    echo "  create-routes  - create network routes to NAT boxes"
    echo "  delete-routes   - delete network routes to NAT boxes."
}

function delete_instance {
    # delete_instance instance-name zone-name
    echo "Deleting $1 in $PROJECT"
    gcloud compute -q --project "$PROJECT" instances delete "$1" --zone "$2"
}
function create_instance {
    # create_instance instance-name zone-name ip-name
    echo "Creating $1 in $PROJECT"
    gcloud compute -q --project "$PROJECT" instances create $1 --project "$PROJECT" --machine-type $INSTANCE_TYPE --zone $2 --image ubuntu-14-04 --network default --can-ip-forward --tags nat --address $3 --metadata-from-file startup-script=nat_startup.sh
}

function create_nat_route {
    # create_nat_route route-name tag instance-name instance-zone
    echo "Creating new route in $PROJECT to hijack traffic from VM tag $2"
    gcloud compute -q --project "$PROJECT" routes create "$1" --network default --destination-range 0.0.0.0/0 --next-hop-instance "$3" --next-hop-instance-zone "$4" --tags "$2" --priority 800
}

function delete_nat_route {
    echo "Deleting routes in $PROJECT: " "$@"
    gcloud compute -q --project "$PROJECT" routes delete "$@"
}

function delete_nat_backend {
    # Deletes NAT routes.
    delete_nat_route managed-vm1-nat-route managed-vm2-nat-route managed-vm3-nat-route
}

function create_nat_backend {
    create_nat_route managed-vm1-nat-route "$GAE_VM1_TAG" nat-box1 "$REGION-a"
    create_nat_route managed-vm2-nat-route "$GAE_VM2_TAG" nat-box2 "$REGION-b"
    create_nat_route managed-vm3-nat-route "$GAE_VM3_TAG" nat-box3 "$REGION-f"
}

# Respin the NAT box VMs. Controlled individually, in case only some
# of them have problems.
function respin_nat1 {
    delete_instance nat-box1 "$REGION-a"
    create_instance nat-box1 "$REGION-a" proxy1
}

function respin_nat2 {
    delete_instance nat-box2 "$REGION-b"
    create_instance nat-box2 "$REGION-b" proxy2
}

function respin_nat3 {
    delete_instance nat-box3 "$REGION-f"
    create_instance nat-box3 "$REGION-f" proxy3
}

cmd=""

case $1 in
    nat1)
	cmd=respin_nat1
	;;
    nat2)
	cmd=respin_nat2
	;;
    nat3)
	cmd=respin_nat3
	;;
    create-routes)
	cmd=create_nat_backend
	;;
    delete-routes)
	cmd=delete_nat_backend
	;;
    *)
	echo "Unknown command: $1. Use nat[1-3], create-routes, delete-routes."
esac

shift
case $1 in
    prod)
        PROJECT=$PROJECT_PROD
        ;;
    dev)
        PROJECT=$PROJECT_DEV        
        ;;
    *)
        cmd=""
        echo "Please specify prod or dev (deployment target)."
esac

if [ -e $cmd ]; then
    print_usage
else
    $cmd
fi

