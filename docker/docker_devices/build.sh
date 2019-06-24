#!/bin/bash -ex
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script will build two docker images, android_docker and cros_docker.
# Both will be tagged with "latest". The root Dockerfile here is used for both,
# but the context directory is specific for each device type so that small
# tweaks can be applied per device.

date=$(/bin/date +"%Y-%m-%d_%H-%M")
par_dir=$(/usr/bin/dirname "${0}")

# Build separate cros_docker and android_docker images. Context directory is
# specific to each device type.
for device in android cros; do
  image="${device}_docker"
  context_dir="${par_dir}/${device}"

  echo "Building for ${device}..."
  /usr/bin/docker build \
    --no-cache=true \
    --pull \
    -t "${image}:${date}" \
    -t "${image}:latest" \
    "${context_dir}" \
    -f "${context_dir}/Dockerfile"
done

exit 0
