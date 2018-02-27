# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import glob
import shutil

from . import platform
from . import source
from . import util

from .builder import Builder, StageWheelForPackage, BuildPackageFromPyPiWheel
from .builder import BuildPackageFromSource

from .types import Spec, UniversalSpec


def SourceOrPrebuiltBuilder(name, version, **kwargs):
  """General-purpose wheel builder.

  If the wheel is "packaged" (see arg for description), it is expected that it
  is resident in PyPi and will be downloaded; otherwise, it will be built from
  source.

  Args:
    name (str): The wheel name.
    version (str): The wheel version.
    packaged (iterable or None): The names of platforms that have this wheel
        available via PyPi. If None, a default set of packaged wheels will be
        generated based on standard PyPi expectations, encoded with each
        Platform's "packaged" property.
    kwargs: Keyword arguments forwarded to Builder.

  Returns (Builder): A configured Builder for the specified wheel.
  """
  pypi_src = source.pypi_sdist(name, version)
  spec = Spec(name=name, version=pypi_src.version, universal=None, default=True)

  packaged = set(kwargs.pop('packaged', (p.name for p in platform.PACKAGED)))

  def build_fn(system, wheel):
    if wheel.plat.name in packaged:
      return BuildPackageFromPyPiWheel(system, wheel)
    return BuildPackageFromSource(system, wheel, pypi_src)

  return Builder(spec, build_fn, **kwargs)


def MultiWheelBuilder(name, version, wheels, only_plat=None, default=True):
  """Builds a wheel consisting of multiple other wheels.

  Bundles can be useful when a user always wants a common set of packages.

  Args:
    name (str): The name of the bundle wheel.
    version (str): The bundle wheel version.
    wheels (iterable): A set of embedded wheel rules to add to the bundle.
    only_plat: (See Builder's "only_plat" argument.)
  """
  spec = Spec(name=name, version=version, universal=None, default=default)

  def build_fn(system, wheel):
    sub_wheels = []
    for w in wheels:
      sub_wheel = w.wheel(system, wheel.plat)
      util.LOGGER.info('Building sub-wheel: %s', sub_wheel)
      sub_wheels += w.build_wheel(sub_wheel, system)
    return sub_wheels

  return Builder(spec, build_fn, only_plat=only_plat)


def PrebuiltBuilder(name, version, only_plat, **kwargs):
  """Wheel builder for prepared wheels that must be downloaded from PyPi.

  Args:
    name (str): The wheel name.
    version (str): The wheel version.
    only_plat: (See Builder's "only_plat" argument.)
    kwargs: Keyword arguments forwarded to Builder.

  Returns (Builder): A configured Builder for the specified wheel.
  """
  spec = Spec(
      name=name,
      version=version,
      universal=None,
      default=True,
  )

  kwargs['only_plat'] = only_plat
  return Builder(spec, BuildPackageFromPyPiWheel, **kwargs)


def UniversalBuilder(name, version, pyversions=None, **kwargs):
  """Universal wheel version of SourceOrPrebuiltBuilder.

  Args:
    name (str): The wheel name.
    version (str): The wheel version.
    pyversions (iterable or None): The list of "python" wheel fields (see
        "Wheel.pyversion_str"). If None, a default Python version will be used.
    kwargs: Keyword arguments forwarded to Builder.

  Returns (Builder): A configured Builder for the specified wheel.
  """
  spec = Spec(
      name=name,
      version=version,
      universal=UniversalSpec(
        pyversions=pyversions,
      ),
      default=True,
  )

  return Builder(spec, BuildPackageFromPyPiWheel, **kwargs)


def UniversalSourceBuilder(name, pypi_version, pyversions=None, pypi_name=None,
                           **kwargs):
  """Universal wheel version of SourceOrPrebuiltBuilder that always builds from
  source.

  Args:
    name (str): The wheel name.
    version (str): The wheel version.
    pyversions (iterable or None): The list of "python" wheel fields (see
        "Wheel.pyversion_str"). If None, a default Python version will be used.
    pypi_name (str or None): Name of the package in PyPi. This can be useful
        when translating between the CIPD package name (uses underscores) and
        the PyPi package name (may use hyphens).
    kwargs: Keyword arguments forwarded to Builder.

  Returns (Builder): A configured Builder for the specified wheel.
  """
  pypi_src = source.pypi_sdist(
      name=pypi_name or name,
      version=pypi_version)

  spec = Spec(
      name=name,
      version=pypi_src.version,
      universal=UniversalSpec(
        pyversions=pyversions,
      ),
      default=True,
  )

  def build_fn(system, wheel):
    return BuildPackageFromSource(system, wheel, pypi_src)

  return Builder(spec, build_fn, **kwargs)
