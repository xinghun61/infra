# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os

from . import cipd

# BINARY_VERSION_SUFFIX is a string added to the end of each version tag. This
# can be used to distinguish one build of a given package from another.
#
# Incrementing BINARY_VERSION only affects binary wheels; it is not applied to
# universal wheels. Changing this is a heavy operation, requiring the user to
# regenerate all wheels for all platforms so that they become available with the
# new suffix.
BINARY_VERSION_SUFFIX = None


UniversalSpec = collections.namedtuple('UniversalSpec', (
    'pyversions'))


_Spec = collections.namedtuple('_Spec', (
    'name', 'version', 'universal',
    # default is true if this Spec should be built by default (i.e., when a
    # user doesn't manually specify Specs to build).
    'default'))
class Spec(_Spec):

  @property
  def tuple(self):
    return (self.name, self.version)

  @property
  def tag(self):
    return '%s-%s' % (self.name, self.version) if self.version else self.name

  def to_universal(self):
    return self._replace(universal=UniversalSpec(pyversions=None))


_Wheel = collections.namedtuple('_Wheel', (
    'spec', 'plat', 'pyversion', 'filename', 'md_lines'))
class Wheel(_Wheel):

  def __new__(cls, *args, **kwargs):
    kwargs.setdefault('md_lines', [])
    return super(Wheel, cls).__new__(cls, *args, **kwargs)

  @property
  def pyversion_str(self):
    if self.spec.universal:
      pyv = self.spec.universal.pyversions
      if pyv is None:
        return 'py2.py3'
      assert 'py2' in pyv
      return 'py2'

    # We only generate wheels for "cpython" at the moment.
    return 'cp%s' % (self.pyversion,)

  @property
  def abi(self):
    if self.spec.universal or not self.plat.wheel_abi:
      return 'none'
    return self.plat.wheel_abi

  @property
  def platform(self):
    return ['any'] if self.spec.universal else self.plat.wheel_plat

  @property
  def primary_platform(self):
    """The platform to use when naming intermediate wheels and requesting
    wheel from "pip". Generally, platforms that this doesn't work on (e.g.,
    ARM) will not have wheels in PyPi, and platforms with wheels in
    PyPi will have only one platform.

    This is also used for naming when building wheels; this choice is
    inconsequential in this context, as the wheel is renamed after the build.
    """
    return self.platform[0]

  def default_filename(self):
    return '%(name)s-%(version)s-%(pyversion)s-%(abi)s-%(platform)s.whl' % {
        'name': self.spec.name.replace('-', '_'),
        'version': self.spec.version,
        'pyversion': self.pyversion_str,
        'abi': self.abi,
        'platform': '.'.join(self.platform),
    }

  def universal_filename(self):
    """This is a universal filename for the wheel, regardless of whether it's
    binary or truly universal. See "A Note on Universality" at the top for
    details on why we'd ever want to do this.
    """
    wheel = self._replace(spec=self.spec.to_universal())
    return wheel.default_filename()

  def path(self, system):
    return os.path.join(system.wheel_dir, self.filename)

  def cipd_package(self, git_revision=None, templated=False):
    base_path = ['infra', 'python', 'wheels']
    if self.spec.universal:
      base_path += ['%s-%s' % (self.spec.name, self.pyversion_str)]
    else:
      base_path += [self.spec.name]
      if not templated:
        base_path += [
          '%s_%s_%s' % (self.plat.cipd_platform, self.pyversion_str, self.abi)]
      else:
        base_path += ['${vpython_platform}']

    version_tag = 'version:%s' % (self.spec.version,)
    if not self.spec.universal and BINARY_VERSION_SUFFIX:
      version_tag += BINARY_VERSION_SUFFIX
    tags = [version_tag]
    if git_revision is not None:
      tags.append('git_revision:%s' % (git_revision,))
    return cipd.Package(
      name=('/'.join(p.replace('.', '_') for p in base_path)).lower(),
      tags=tuple(tags),
      install_mode=cipd.INSTALL_SYMLINK,
      compress_level=cipd.COMPRESS_NONE,
    )


