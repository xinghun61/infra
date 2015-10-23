# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import shutil
import tempfile


from infra.tools.cros_pin import execute
from infra.tools.cros_pin.logger import LOGGER


class Checkout(object):
  """Checkout is a managed root checkout directory."""

  GCLIENT_TEMPLATE = """
solutions = [
  {
    "url": "https://chromium.googlesource.com/chromium/tools/build.git",
    "managed": False,
    "name": "build",
    "deps_file": ".DEPS.git",
  },
  {
    "url": "https://chrome-internal.googlesource.com/chrome/tools/build.git",
    "managed": False,
    "name": "build_internal",
    "deps_file": ".DEPS.git",
  },
]
"""

  def __init__(self, path, delete=False):
    self._path = path
    self._delete = delete

  @property
  def path(self):
    return self._path

  def subpath(self, *components):
    return os.path.join(self._path, *components)

  def teardown(self):
    if self._delete:
      self._destroy_directory(self._path)

  @classmethod
  @contextlib.contextmanager
  def use(cls, *args, **kwargs):
    c = None
    try:
      c = cls.create(*args, **kwargs)
      LOGGER.debug('Using checkout at: %s', c.path)
      yield c
    finally:
      if c:
        c.teardown()

  @classmethod
  def create(cls, path=None):
    """Creates a new Checkout using the specified path.

    Args:
      path (str): The path of the checkout to use. If None, a temporary
          checkout will be created.
    """
    delete = False
    if path:
      if os.path.isdir(path):
        return cls(path, delete=False)
      os.makedirs(path)
    else:
      path = tempfile.mkdtemp(prefix='tmp_cros_pin')
      delete = True

    try:
      cls.fetch(path)
      c = cls(path, delete=delete)
      path = None # Signal our "finally" clause not to clean up here.
    finally:
      if path:
        cls._destroy_directory(path)
    return c

  @classmethod
  def fetch(cls, path):
    LOGGER.info("Fetching => %s (This can take a while.)", path)
    gclient_path = os.path.join(path, '.gclient')
    with open(gclient_path, 'w') as fd:
      fd.write(cls.GCLIENT_TEMPLATE)

    execute.check_call(
        ['gclient', 'sync', '--nohooks', '--noprehooks'],
        cwd=path)

  @staticmethod
  def _destroy_directory(d):
    LOGGER.debug('Destorying directory: %s', d)
    def log_failure(_function, path, excinfo):
      LOGGER.warning('Failed when destroying [%s]: %s',
                     path, excinfo[1].message)
    shutil.rmtree(d, onerror=log_failure)
