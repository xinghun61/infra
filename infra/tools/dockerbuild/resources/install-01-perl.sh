#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Install system Perl into "PREFIX".
#
# This is needed by the "cryptography" package, since the PERL on some of the
# dockcross images does not meet minimum version requirements.
#
# This script consumes:
# - ARCHIVE_PATH is the path to the Perl archive file.

# Load our installation utility functions.
. /install-util.sh

if [ -z "${ARCHIVE_PATH}" ]; then
  echo "ERROR: Missing required environment."
  exit 1
fi

ROOT=${PWD}

# Unpack our archive and enter its base directory (whatever it is named).
tar -xzf ${ARCHIVE_PATH}
cd $(get_archive_dir ${ARCHIVE_PATH})

# Build and install host Perl.
toggle_host

./Configure \
  -des \
  "-Dprefix=${LOCAL_PREFIX}"
make -j$(nproc)
make install
