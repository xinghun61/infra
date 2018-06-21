# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from . import source
from . import builder
from . import util

from . import wheel_wheel

from .builder import Builder
from .types import Spec, UniversalSpec


def InfraBuilder(name):
  """Wheel builder for pure Python wheels built from the current local repo's
     packages folder.

  Args:
    name (str): The wheel name.
  """
  spec = Spec(
      name=name,
      version=None,
      universal=UniversalSpec(pyversions=['py2']),
      default=True,
  )

  def _local_path(system):
    return os.path.join(os.path.dirname(system.root), 'packages', name)

  version_ref = [None]
  def version_fn(system):
    if version_ref[0] is None:
      pkg_path = os.path.join(os.path.dirname(system.root), 'packages', name)
      _, version_ref[0] = util.check_run(
          system,
          None,
          '.',
          ['python', os.path.join(pkg_path, 'setup.py') , '--version']
      )
    return version_ref[0]

  def build_fn(system, wheel):
    path = _local_path(system)
    src = source.local_directory(name, wheel.spec.version, path)
    return builder.BuildPackageFromSource(system, wheel, src)

  return Builder(spec, build_fn, version_fn=version_fn)
