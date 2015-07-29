#!/bin/bash

DOCKER_LOG='docker_build.log'
PROJECT_DEV="chrome-infra-mon-proxy-dev"
PROJECT_PROD="chrome-infra-mon-proxy"
MANIFEST_TEMPLATE="monitoring_proxy_containers.yaml.template"
MANIFEST_DEV="monitoring_proxy_containers_dev.yaml"
MANIFEST_PROD="monitoring_proxy_containers_prod.yaml"
PROXY_BINARY="proxy"
REGION="us-central1"
INSTANCE_TYPE="n1-standard-2"

function print_usage {
    echo
    echo "Usage:"
    echo "$0 dev|prod"
}

function _run_check {
    $*
    RV=$?
    if [ ${RV} != 0 ]; then
        echo -e "ERROR: [$*] returned with non-zero ${RV}"
        exit 1
    fi
}

function docker_build {
  rm -f "$DOCKER_LOG"
  if ! [ -f "$PROXY_BINARY" ]; then
      echo "Error: executable '$PROXY_BINARY' does not exist."
      return
  fi
  _run_check chmod u+x "$PROXY_BINARY"
  # For good measure.
  _run_check chmod u+x monitoring_proxy.sh

  _run_check docker build . | tee -a "$DOCKER_LOG"

  image_hash=`grep 'Successfully built' $DOCKER_LOG | awk '{print $3;}'`
  if [ -z $image_hash ]; then
      echo "Error: did not find new image hash. See $DOCKER_LOG for details."
      exit 1
  fi
  image_tag=gcr.io/`echo $PROJECT | tr - _`/monitoring_proxy_go_$image_hash
  docker tag $image_hash $image_tag
  if [ $? != 0 ]; then
      echo "ERROR: The docker image did not change. "
      echo "If needed, upload the image manually:"
      echo "   gcloud --project "$PROJECT" docker push $image_tag"
      exit 1
  fi
  _run_check gcloud --project "$PROJECT" docker push "$image_tag"
  cat "$MANIFEST_TEMPLATE" | sed -e "s@%image_tag%@$image_tag@" > "$MANIFEST"
  echo
  echo "Done. Updated '$MANIFEST' with new image tag:"
  echo "$image_tag"
  echo "Deploy the new container with ./setup {dev|prod}."
}

case $1 in
    prod)
        PROJECT="$PROJECT_PROD"
        MANIFEST="$MANIFEST_PROD"
        docker_build
        ;;
    dev)
        PROJECT="$PROJECT_DEV"
        MANIFEST="$MANIFEST_DEV"
        docker_build
        ;;
    *)
        echo "Please specify dev or prod (deployment target)."
        print_usage
        exit 1
esac
