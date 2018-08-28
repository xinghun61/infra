#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Build host and cross-compile Python installations.
#
# This script consumes:
# - ARCHIVE_PATH is the path to the Python archive file.
# - CROSS_UNICODE is the Unicode setting value to configure the cross-compile
#   Python with.
# - CROSS_CONFIG_SITE is the path to the "config.site" file to use for
#   cross-compiling.
#
# This script expects to be called in a host build environment.
#
# We build both Python installations in a single script because the
# cross-compile Python requires some host Python files in order to work
# properly.

# Load our installation utility functions.
. /install-util.sh

if \
  [ -z "${ARCHIVE_PATH}" ] || \
  [ -z "${CROSS_UNICODE}" ] || \
  [ -z "${CROSS_CONFIG_SITE}" ]; then
  echo "ERROR: Missing required environment."
  exit 1
fi

# Resolve CROSS_CONFIG_SITE to absolute path, since we will reference it after
# we chdir.
CROSS_CONFIG_SITE=$(abspath ${CROSS_CONFIG_SITE})

ROOT=${PWD}

# Unpack our archive and enter its base directory (whatever it is named).
tar -xzf ${ARCHIVE_PATH}
cd $(get_archive_dir ${ARCHIVE_PATH})

##
# Build Host Python
##

toggle_host

# We use the same Unicode spec as our cross-compile enviornment b/c wheel
# building looks at the *build* compiler's spec, not the target platform's
# spec, to determine what the unicode size is :(
./configure \
  --prefix="${LOCAL_PREFIX}" \
  --enable-unicode="${CROSS_UNICODE}"
make -j$(nproc)
make install

##
# Build Cross-compile Python
##

toggle_cross

# (Cross) We preserve the host's "pybuilddir.txt" because of a bug in Python's
# cross-compile code. Currently, that file points to local (builder) versions
# of compiled Python libraries from the previous compile. During the
# cross-compile build, it will point to the cross-compile subdirectory instead.
# Then, when Python tries to actually run its own scripts, it will use the
# cross-compile directory for its PYTHONPATH instead of the builder directory
# (see Makefile).
cp pybuilddir.txt host-pybuilddir.txt

CONFIG_SITE=${CROSS_CONFIG_SITE} \
  ./configure \
  --prefix="${CROSS_PREFIX}" \
  --host=${CROSS_TRIPLE} \
  --build=$(gcc -dumpmachine) \
  --enable-unicode="${CROSS_UNICODE}" \
  --disable-ipv6
make -j$(nproc)

# Restore "pybuilddir.txt" and build for installation. Since this invalidates
# some of the built artifacts, but we can't "make install" with multiple jobs,
# re-run "make" first as an optimization.
cp host-pybuilddir.txt pybuilddir.txt
make -j$(nproc)
make install
