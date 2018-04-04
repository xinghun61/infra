# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from .types import Spec
from .builder import Builder

from . import util
from . import wheel_wheel
from . import source

from .builder import StageWheelForPackage

def MySQLPythonBuilder(version, **kwargs):
  """Exactly like SourceOrPrebuiltBuilder, except links MySQL-python
  statically.

  Args:
    version (str): The MySQL-python version.
    kwargs: Keyword arguments forwarded to Builder.

  Returns (Builder): A configured Builder for the specified wheel.
  """
  name = 'MySQL-python'
  pypi_src = source.pypi_sdist(name, version)
  spec = Spec(name=name, version=pypi_src.version, universal=None, default=True)

  def build_fn(system, wheel):
    return _build_mysql(system, wheel, pypi_src)

  return Builder(spec, build_fn, **kwargs)


def _build_mysql(system, wheel, src):
  dx = system.dockcross_image(wheel.plat)
  assert dx, "Docker required for MySQL-python"
  with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
    build_dir = system.repo.ensure(src, tdir)

    with open(os.path.join(build_dir, 'site.cfg'), 'r+b') as f:
      current = f.readlines()
      f.truncate()
      f.seek(0)
      for line in current:
        if line.startswith('static'):
          f.write('static = True\n')
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
        cwd=build_dir)

    StageWheelForPackage(system, tdir, wheel)


