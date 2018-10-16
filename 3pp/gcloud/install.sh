#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

# Augment the default (installation) properties.
#
# NOTE: Currently this builder is OS-agnostic (e.g., a Linux builder can build
# a Windows package). For now, we will keep it that way by manually updating the
# properties file.
#
# If we ever need to actually run "gcloud" commands to update properties, we can
# make this packager OS-specific and run "gcloud" in the now-unpacked bundle.
#
# Commands are:
# $ ./bin/gcloud config set  component_manager/disable_update_check true \
#   --installation
cat >> google-cloud-sdk/properties <<EOF
[component_manager]
disable_update_check = True
EOF

cp -a google-cloud-sdk "$PREFIX"/
