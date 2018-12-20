# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from .types import Spec
from .builder import Builder

from . import util
from . import source

from .builder import StageWheelForPackage


class MySQLPython(Builder):
  def __init__(self, version, **kwargs):
    """Exactly like SourceOrPrebuiltBuilder, except links MySQL-python
    statically.

    Args:
      version (str): The MySQL-python version.
      kwargs: Keyword arguments forwarded to Builder.
    """
    name = 'MySQL-python'
    self._pypi_src = source.pypi_sdist(name, version)
    super(MySQLPython, self).__init__(
      Spec(name, self._pypi_src.version, universal=None, default=True),
      **kwargs)

  def build_fn(self, system, wheel):
    dx = system.dockcross_image(wheel.plat)
    assert dx, "Docker required for MySQL-python"
    with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
      build_dir = system.repo.ensure(self._pypi_src, tdir)

      # Adjust site.cfg to have static=True && threadsafe=False.
      #
      # Static because we don't want to link in the libmysqlclient.so, and
      # threadsafe because:
      #   1) MySQL 5.ancient became threadsafe by default. The threadsafe and
      #      non-threadsafe libraries are henceforth symlinked together.
      #   2) MySQL-python has a bug where static&&threadsafe ends up linking
      #      against the .so file by accident instead of the .a, thus ruining
      #      all of our fabulous plans.
      with open(os.path.join(build_dir, 'site.cfg'), 'r+b') as f:
        current = f.readlines()
        f.truncate(0)
        f.seek(0)
        for line in current:
          if line.startswith('static'):
            f.write('static = True\n')
          elif line.startswith('threadsafe'):
            f.write('threadsafe = False\n')
          else:
            f.write(line)

      cmd = [
        'python', '-m', 'pip', 'wheel',
        '--no-deps',
        '--only-binary=:all:',
        '--wheel-dir', tdir,
        '.',
      ]

      util.check_run(
          system,
          dx,
          tdir,
          cmd,
          cwd=build_dir,
          env={
            'LDFLAGS': '-lstdc++'
          })

      StageWheelForPackage(system, tdir, wheel)
