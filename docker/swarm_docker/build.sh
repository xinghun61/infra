#!/bin/bash -ex
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

date=$(/bin/date +"%Y-%m-%d_%H-%M")
par_dir="$(dirname "${0}")"

echo "Building for swarm_docker..."
/usr/bin/docker build \
  --no-cache=true \
  --pull \
  -t "swarm_docker:${date}" \
  -t swarm_docker:latest \
  "${par_dir}"

exit 0
