# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from . import util

from . import wheel_wheel

from .types import Spec
from .builder import Builder


def OpenCVBuilder(name, version, numpy_version, packaged=None,
                  arch_map=None, only_plat=None, skip_plat=None):
  """Specialized wheel builder for the "OpenCV" package.

  Args:
    name (str): The wheel name.
    version (str): The OpenCV version (must be a Git tag within the source).
    numpy_version (str): The "numpy" wheel version to build against.
        version will be extracted from this.
    packaged (iterable or None): The names of platforms that have this wheel
        available via PyPi. If None, will build from source for all platforms.
    arch_map: (See Builder's "arch_map" argument.)
    only_plat: (See Builder's "only_plat" argument.)
    skip_plat (iterable or None): If not None, this Builder will avoid declaring
        that it can build for the named platforms.

  Returns (Builder): A configured Builder for the specified wheel.
  """
  spec = Spec(name=name, version=version, universal=None, default=True)

  def build_fn(system, wheel):
    if wheel.plat.name in (packaged or ()):
      return wheel_wheel.BuildPackageFromPyPi(system, wheel)
    return _build_opencv(system, wheel, numpy_version)

  return Builder(spec, build_fn, arch_map=arch_map, only_plat=only_plat,
                 skip_plat=skip_plat)


def _build_opencv(system, wheel, numpy_version):
  # See "resources/build-opencv.sh" for more information.
  opencv_python = (
      'infra/third_party/source/opencv_python_repo',
      'git_revision:83b0ac8a200195d466bd7b4b5ac26923c98f0a64')
  virtualenv = (
        'infra/python/virtualenv',
        'version:15.1.0')

  # Build our "numpy" wheel.
  numpy_builder = wheel_wheel.BuildWheel('numpy', numpy_version)
  numpy_wheel = numpy_builder.wheel(system, wheel.plat)
  numpy_builder.build(numpy_wheel, system)
  numpy_path = numpy_wheel.path(system)

  dx = system.dockcross_image(wheel.plat)
  with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
    # Copy external resources into "tdir" (workdir).
    script_path = util.copy_to(util.resource_path('build-opencv.sh'), tdir)
    numpy_path = util.copy_to(numpy_path, tdir)

    # Get OpenCV source and check out the correct version.
    opencv_path = os.path.join(tdir, 'opencv_cipd')
    system.cipd.install(opencv_python[0], opencv_python[1], opencv_path)
    opencv_path = util.copy_to(opencv_path, os.path.join(tdir, 'opencv'))

    # Get VirtualEnv source.
    venv_root = os.path.join(tdir, 'virtualenv')
    system.cipd.install(virtualenv[0], virtualenv[1], venv_root)
    venv_path = os.path.join(venv_root, 'virtualenv-15.1.0')

    # Run our build script.
    workdir = util.ensure_directory(tdir, 'workdir')
    util.check_run(
        system,
        dx,
        tdir,
        [
          'sh',
          script_path,
          workdir,
          opencv_path,
          wheel.spec.version,
          venv_path,
          numpy_path,
        ],
    )

    wheel_wheel.StageWheelForPackage(
        system, os.path.join(workdir, 'wheel', 'dist'), wheel)


