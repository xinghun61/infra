# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import contextlib
import hashlib
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
LOCAL_OBJECT_URL = 'file://{}'

LOCAL_STORAGE_PATH = os.path.join(ROOT, 'wheelhouse_cache')

SOURCE_URL = 'gs://{}/sources/{{}}'.format(BUCKET)
WHEELS_URL = 'gs://{}/wheels/'.format(BUCKET)

# Chunk size to read files.
CHUNK_SIZE = 4*1024*1024

class DepsConflictException(Exception):
  def __init__(self, name):
    super(DepsConflictException, self).__init__(
        'Package \'%s\' is defined twice in deps.pyl' % name)


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


def build_manifest(deps):
  # Derive information about the current Python interpreter.
  interp_hash = hashlib.sha256()
  with open(sys.executable, 'rb') as fd:
    while True:
      chunk = fd.read(CHUNK_SIZE)
      interp_hash.update(chunk)
      if len(chunk) < CHUNK_SIZE:
        break

  return {
      'interpreter': {
        'path': sys.executable,
        'hash_sha256': interp_hash.hexdigest(),
      },
      'deps': deps,
  }


def read_python_literal(path):
  if os.path.exists(path):
    with open(path, 'rb') as f:
      return ast.literal_eval(f.read())


def merge_deps(paths):
  deps = {}
  for path in paths:
    d = read_python_literal(path)
    for key in d:
      if key in deps:
        raise DepsConflictException(key)
    deps.update(d)
  return deps


def filter_deps(deps, tag_to_check):
  out = {}
  kicked = {}
  for pkg, dep in deps.iteritems():
    p = dep.get('only_on', None)
    if not p or tag_to_check in p:
      out[pkg] = dep
    else:
      kicked[pkg] = dep
  return out, kicked
