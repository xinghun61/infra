# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys


# Path to root of the "infra" repository.
INFRA_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir))
RUN_PY = os.path.join(INFRA_ROOT, 'run.py')


def call(args, **kwargs):
  print 'Running %s' % ' '.join(args)
  if kwargs.get('cwd'):
    print '  In %s' % kwargs.get('cwd')
  kwargs.setdefault('stdout', subprocess.PIPE)
  kwargs.setdefault('stderr', subprocess.STDOUT)
  proc = subprocess.Popen(args, **kwargs)
  while True:
    buf = proc.stdout.read(1)
    if not buf:
      break
    sys.stdout.write(buf)
  return proc.wait()


def rmtree(target, ignore_errors=False):
  """Recursively deletes a target using "infra.tools.rmtree"."""
  rc = call([RUN_PY, 'infra.tools.rmtree', '--logs-verbose', '--try-as-root',
            target])
  if rc == 0 or ignore_errors:
    return rc
  raise Exception('Failed to delete directory %r (rc=%d)' % (target, rc))
