# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re


Package = collections.namedtuple('Package', (
    'name', 'tags', 'install_mode', 'compress_level'))


# "compress_level" value for "no compression".
COMPRESS_NONE = 0


INSTALL_SYMLINK = 'symlink'
INSTALL_COPY = 'copy'


RE_DISALLOWED_PACKAGE_CHARS = re.compile(r'^[a-zA-Z-_]')


def normalize_package_name(name):
  return RE_DISALLOWED_PACKAGE_CHARS.sub(name.lower(), '-')


class Cipd(object):

  def __init__(self, system, cache_dir):
    self._system = system
    self._cache_dir = cache_dir
    self._exists_cache = set()

  def _run_cipd(self, run_fn, args):
    return run_fn(
        [self._system.tools.cipd] + list(args),
        env={'CIPD_CACHE_DIR': self._cache_dir})

  def run(self, *args):
    return self._run_cipd(self._system.run, args)

  def check_run(self, *args):
    return self._run_cipd(self._system.check_run, args)

  def exists(self, name, *versions):
    if any((name, v) in self._exists_cache for v in versions):
      return True

    for v in versions:
      rc, _ = self.run('resolve', name, '-version', v)
      if not rc:
        self._exists_cache.add((name, v))
        return True
    return False

  def create(self, package, root):
    cmd = [
        'create',
        '-compression-level', str(package.compress_level),
        '-in', root,
        '-install-mode', package.install_mode,
        '-name', package.name,
    ]
    for tag in package.tags or ():
      cmd += ['-tag', tag]
    self.check_run(*cmd)

  def install(self, name, version, root):
    self.check_run('install', '-root', root, name, version)

  def register_package(self, path, *tags):
    cmd = [
        'pkg-register',
        path,
    ]
    for tag in tags:
      cmd += ['-tag', tag]
    self.check_run(*cmd)

  def create_package(self, package, src_dir, pkg_path):
    self.check_run(
        'pkg-build',
        '-compression-level', str(package.compress_level),
        '-in', src_dir,
        '-install-mode', package.install_mode,
        '-name', package.name,
        '-out', pkg_path,
    )

  def fetch_package(self, name, version, path):
    self.check_run(
        'pkg-fetch',
        '-version', version,
        '-out', path,
        name,
    )

  def deploy_package(self, path, root):
    self.check_run('pkg-deploy', '-root', root, path)
