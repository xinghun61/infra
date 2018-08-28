#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Install system MySQL into "PREFIX".
#
# This is needed by the "MySQL-python" package, since the MySQL version's static
# libraries aren't linked correctly on x64 systems (need -fPIC).
#
# This script consumes:
# - ARCHIVE_PATH is the path to the MySQL archive file.

# Load our installation utility functions.
. /install-util.sh

if echo ${CROSS_TRIPLE} | grep mipsel; then
  # mipsel has trouble compiling MySQL, so skip it
  exit
fi

if [ -z "${ARCHIVE_PATH}" -o -z "${BOOST_PATH}" ]; then
  echo "ERROR: Missing required environment."
  exit 1
fi

# Unpack our archive and enter its base directory (whatever it is named).
tar xf "${ARCHIVE_PATH}"
tar xf "${BOOST_PATH}"
BOOST_NAME=$(get_archive_dir ${BOOST_PATH})

cd $(get_archive_dir ${ARCHIVE_PATH})

mv ../${BOOST_NAME} ./

# Build all native MySQL tools/tests
toggle_host

cmake \
  -DWITH_UNIT_TESTS=OFF -DWITHOUT_SERVER=1 \
  -DWITH_BOOST="${BOOST_NAME}"
make -j$(nproc)

# Now, reconfig for cross-compile.
toggle_cross

rm CMakeCache.txt
cmake \
  -DWITH_UNIT_TESTS=OFF -DWITHOUT_SERVER=1 \
  -DWITH_BOOST="${BOOST_NAME}" \
  -DSTACK_DIRECTION=1

# There are a couple tests which are set to POST_BUILD... unfortunately they
# won't work when we cross compile. So just cheat a bit :)
mv ./libmysql/libmysql_api_test{,.bak}
mv ./mysys/base64_test{,.bak}

PATH="$(pwd)/extra:$(pwd)/scripts:${PATH}" make -j$(nproc) || true

mv ./libmysql/libmysql_api_test{.bak,}
mv ./mysys/base64_test{.bak,}
touch ./libmysql/libmysql_api_test ./mysys/base64_test

PATH="$(pwd)/extra:$(pwd)/scripts:${PATH}" make -j$(nproc) install

# MySQL-Python still links the old _r versions of the libraries. As of MySQL 5.5
# these no longer exist, and the manual suggests just symlinking them together.
#
# Give the people what they want, I guess?
ln -s /usr/local/mysql/lib/libmysqlclient{,_r}.a
