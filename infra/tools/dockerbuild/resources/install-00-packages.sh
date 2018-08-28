#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Load our installation utility functions.
. /install-util.sh

# Install missing packages for system Python modules.
#
# For CentOS, "dockcross" currently uses CentOS 5.11, which is end-of-life. We
# have to update its repositories to point to the CentOS vault in order for
# "yum" to work.
if [ -x /usr/bin/apt-get ]; then
  apt-get install -y zlib1g-dev libbz2-dev
  apt-get clean --yes
elif [ -x /usr/bin/yum ]; then
  yum install -y zlib-devel bzip2-devel
  yum clean all
else
  echo "UKNOWN package platform."
  exit 1
fi

# The CentOS images also don't have `nproc`, so add it.
if ! which nproc; then
  echo '#!/bin/bash' > /usr/bin/nproc
  echo 'grep processor < /proc/cpuinfo | wc -l' >> /usr/bin/nproc
  chmod +x /usr/bin/nproc
fi
