#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import hashlib
import os
import subprocess
import sys

BUCKET = 'gs://chrome-python-wheelhouse/sources/'


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('path', nargs='+',
                      help='Location of the archive to upload')
  o = parser.parse_args()

  for path in o.path:
    fname = os.path.basename(path)

    with open(path, 'rb') as f:
      data = f.read()

    sha = hashlib.sha1(data).hexdigest()
    bits = []
    for bit in reversed(fname.split('.')):
      if bit in ('tar', 'gz', 'tgz', 'zip', 'bz2'):
        bits.insert(0, bit)
      else:
        break
    ext = '.' + '.'.join(bits)

    new_fname = sha + ext
    cmd = ['gsutil', 'cp', '-', BUCKET + new_fname]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    out, _ = proc.communicate(data)
    if proc.returncode != 0:
      raise subprocess.CalledProcessError(proc.returncode, cmd, out)

    print

    print new_fname


if __name__ == '__main__':
  sys.exit(main())
