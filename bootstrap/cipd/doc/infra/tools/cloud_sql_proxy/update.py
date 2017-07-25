#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Downloads cloud_sql_proxy for Linux and Mac, and packages it as cipd.

See https://cloud.google.com/sql/docs/mysql/sql-proxy#install

It's an unversioned binary. So we just tag it with the current date.
"""

import os
import shutil
import subprocess
import tempfile
import time
import urllib


def package(url, exe, pkg, tag):
  tmp = tempfile.mkdtemp(prefix='cloud_sql_proxy_upload')
  try:
    print 'Fetching %s...' % url
    urllib.urlretrieve(url, os.path.join(tmp, exe))
    os.chmod(os.path.join(tmp, exe), 0777)
    print 'Packaging it as %s and tagging with %s' % (pkg, tag)
    subprocess.check_call([
        'cipd', 'create',
        '-in', tmp,
        '-name', pkg,
        '-tag', tag,
    ])
  finally:
    shutil.rmtree(tmp)


def main():
  tag = time.strftime('downloaded:%Y_%m_%d')
  package(
      url='https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64',
      exe='cloud_sql_proxy',
      pkg='infra/tools/cloud_sql_proxy/linux-amd64',
      tag=tag)
  package(
      url='https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64',
      exe='cloud_sql_proxy',
      pkg='infra/tools/cloud_sql_proxy/mac-amd64',
      tag=tag)


if __name__ == '__main__':
  main()
