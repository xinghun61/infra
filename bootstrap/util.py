# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import contextlib
import os
import platform
import shutil
import sys
import tempfile


ROOT = os.path.dirname(os.path.abspath(__file__))
WHEELHOUSE = os.path.join(ROOT, 'wheelhouse')

BUCKET = 'chrome-python-wheelhouse'
STORAGE_URL = 'https://www.googleapis.com/storage/v1/b/{}/o'.format(BUCKET)
OBJECT_URL = 'https://storage.googleapis.com/{}/{{}}#md5={{}}'.format(BUCKET)

GIT_REPO = 'git+https://chromium.googlesource.com/infra/third_party/{}'
SOURCE_URL = 'gs://{}/sources/{{}}'.format(BUCKET)
WHEELS_URL = 'gs://{}/wheels/'.format(BUCKET)


def platform_tag():
  if sys.platform.startswith('linux'):
    return '_{0}_{1}'.format(*platform.linux_distribution())
  return ''


def print_deps(deps, indent=1, with_implicit=True):
  for dep, entry in deps.iteritems():
    if not with_implicit and entry.get('implicit'):
      continue
    print '  ' * indent + '%s: %r' % (dep, entry)
  print


@contextlib.contextmanager
def tempdir(*args, **kwargs):
  tdir = None
  try:
    tdir = tempfile.mkdtemp(*args, **kwargs)
    yield tdir
  finally:
    if tdir:
      shutil.rmtree(tdir, ignore_errors=True)


@contextlib.contextmanager
def tempname(*args, **kwargs):
  tmp = None
  try:
    tmp = tempfile.mktemp(*args, **kwargs)
    yield tmp
  finally:
    if tmp:
      try:
        os.unlink(tmp)
      except OSError:
        pass


def read_deps(path):
  if os.path.exists(path):
    with open(path, 'rb') as f:
      return ast.literal_eval(f.read())
