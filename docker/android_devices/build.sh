#!/bin/sh -x
date=$(/bin/date +"%Y-%m-%d_%H-%M")
IMAGE=android_docker
DOCKER_BIN_PATH=/usr/bin/docker

if [ "$1" = "-n" ]; then
  cache="--no-cache=true"
  shift
else
  cache="--no-cache=false"
fi

$DOCKER_BIN_PATH build $cache -t ${IMAGE}:${date} .
$DOCKER_BIN_PATH tag ${IMAGE}:$date ${IMAGE}:latest
exit 0
