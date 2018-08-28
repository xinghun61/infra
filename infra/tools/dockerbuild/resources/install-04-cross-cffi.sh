#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Install the Python "cffi" package.
#
# This script consumes:
# - ARCHIVE_PATH is the path to the "cffi" archive file.
# - XPYTHONPATH is the path to the cross-compile Python's site packages.

# Load our installation utility functions.
. /install-util.sh

if \
  [ -z "${ARCHIVE_PATH}" ] || \
  [ -z "${XPYTHONPATH}" ]; then
  echo "ERROR: Missing required environment."
  exit 1
fi

ROOT=${PWD}

# Unpack our archive and enter its base directory (whatever it is named).
tar -xzf ${ARCHIVE_PATH}
cd $(get_archive_dir ${ARCHIVE_PATH})

export PYTHONPATH=${XPYTHONPATH}
python \
  setup.py install \
  --prefix=${CROSS_PREFIX}
