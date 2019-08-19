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


class SourceOrPrebuilt(Builder):
  def __init__(self, name, version, **kwargs):
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
      env (Dict[str, str]|None): Envvars to set when building the wheel from
          source.
      kwargs: Keyword arguments forwarded to Builder.
    """
    self._pypi_src = source.pypi_sdist(name, version)
    self._packaged = set(
      kwargs.pop('packaged', (p.name for p in platform.PACKAGED)))
    self._env = kwargs.pop('env', None)

    super(SourceOrPrebuilt, self).__init__(
      Spec(name, self._pypi_src.version, universal=None, default=True),
      **kwargs)

  def build_fn(self, system, wheel):
    if wheel.plat.name in self._packaged:
      return BuildPackageFromPyPiWheel(system, wheel)
    return BuildPackageFromSource(system, wheel, self._pypi_src, self._env)


class MultiWheel(Builder):
  def __init__(self, name, version, wheels, only_plat=None, default=True):
    """Builds a wheel consisting of multiple other wheels.

    Bundles can be useful when a user always wants a common set of packages.

    Args:
      name (str): The name of the bundle wheel.
      version (str): The bundle wheel version.
      wheels (iterable): A set of embedded wheel rules to add to the bundle.
      only_plat: (See Builder's "only_plat" argument.)
    """
    self._wheels = wheels
    super(MultiWheel, self).__init__(
      Spec(name, version, universal=None, default=default),
      only_plat=only_plat)

  def build_fn(self, system, wheel):
    sub_wheels = []
    for w in self._wheels:
      sub_wheel = w.wheel(system, wheel.plat)
      util.LOGGER.info('Building sub-wheel: %s', sub_wheel)
      sub_wheels += w.build_wheel(sub_wheel, system)
    return sub_wheels


class Prebuilt(Builder):
  """Wheel builder for prepared wheels that must be downloaded from PyPi.

  Args:
    name (str): The wheel name.
    version (str): The wheel version.
    only_plat: (See Builder's "only_plat" argument.)
    kwargs: Keyword arguments forwarded to Builder.
  """
  def __init__(self, name, version, only_plat, **kwargs):
    kwargs['only_plat'] = only_plat
    super(Prebuilt, self).__init__(
      Spec(name, version, universal=None, default=True),
      **kwargs)

  def build_fn(self, system, wheel):
    return BuildPackageFromPyPiWheel(system, wheel)


class Universal(Builder):
  def __init__(self, name, version, pyversions=None, **kwargs):
    """Universal wheel version of SourceOrPrebuilt.

    Args:
      name (str): The wheel name.
      version (str): The wheel version.
      pyversions (iterable or None): The list of "python" wheel fields (see
          "Wheel.pyversion_str"). If None, a default Python version will be
          used.
      kwargs: Keyword arguments forwarded to Builder.
    """
    super(Universal, self).__init__(Spec(
        name, version,
        universal=UniversalSpec(pyversions=pyversions),
        default=True,
    ), **kwargs)

  def build_fn(self, system, wheel):
    return BuildPackageFromPyPiWheel(system, wheel)


class UniversalSource(Builder):
  def __init__(self, name, pypi_version, pyversions=None, pypi_name=None,
               patches=(), **kwargs):
    """Universal wheel version of SourceOrPrebuilt that always builds from
    source.

    Args:
      name (str): The wheel name.
      version (str): The wheel version.
      pyversions (iterable or None): The list of "python" wheel fields (see
          "Wheel.pyversion_str"). If None, a default Python version will be
          used.
      pypi_name (str or None): Name of the package in PyPi. This can be useful
          when translating between the CIPD package name (uses underscores) and
          the PyPi package name (may use hyphens).
      patches (tuple): Short patch names to apply to the source tree.
      kwargs: Keyword arguments forwarded to Builder.

    Returns (Builder): A configured Builder for the specified wheel.
    """
    self._pypi_src = source.pypi_sdist(
        name=pypi_name or name,
        version=pypi_version,
        patches=patches)
    super(UniversalSource, self).__init__(Spec(
        name, self._pypi_src.version,
        universal=UniversalSpec(pyversions=pyversions),
        default=True,
    ), **kwargs)

  def build_fn(self, system, wheel):
    return BuildPackageFromSource(system, wheel, self._pypi_src)

  def version_fn(self, _system):
    return self._pypi_src.buildid

  def md_data_fn(self):
    if not self._pypi_src.patches:
      return []

    return ['\n* custom patches: %s' % (', '.join(self._pypi_src.patches),)]
