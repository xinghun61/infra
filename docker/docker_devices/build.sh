#!/bin/sh -x

# This script will build two docker images, android_docker and cros_docker.
# Both will be tagged with "latest". The root Dockerfile here is used for both,
# but the context directory is specific for each device type so that small
# tweaks can be applied per device.

date=$(/bin/date +"%Y-%m-%d_%H-%M")
DOCKER_BIN_PATH=/usr/bin/docker

if [ "$1" = "-n" ]; then
  cache="--no-cache=true"
  shift
else
  cache="--no-cache=false"
fi

par_dir=$(dirname $0)

# Build separate cros_docker and android_docker images. Context directory is
# specific to each device type.
for device in "android" "cros"; do
  image=$device"_docker"
  context_dir=$par_dir"/"$device
  docker_file=$par_dir"/"Dockerfile
  $DOCKER_BIN_PATH build -f - $cache -t ${image}:${date} ${context_dir} < $docker_file
  $DOCKER_BIN_PATH tag ${image}:$date ${image}:latest
done

exit 0
