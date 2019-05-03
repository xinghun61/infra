# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from .types import Spec
from .builder import Builder, BuildPackageFromPyPiWheel, StageWheelForPackage

from . import source
from . import util

class Cryptography(Builder):
  def __init__(self, name, crypt_src, openssl_src, packaged=None,
               arch_map=None):
    """Specialized wheel builder for the "cryptography" package.

    Args:
      name (str): The wheel name.
      crypt_src (Source): The Source for the cryptography package. The wheel
          version will be extracted from this.
      openssl_src (Source): The OpenSSL source to build against.
      packaged (iterable or None): The names of platforms that have this wheel
          available via PyPi. If None, a default set of packaged wheels will be
          generated based on standard PyPi expectations, encoded with each
          Platform's "packaged" property.
      arch_map: (See Builder's "arch_map" argument.)
    """
    self._packaged = packaged or ()
    self._crypt_src = crypt_src
    self._openssl_src = openssl_src
    super(Cryptography, self).__init__(
      Spec(name, crypt_src.version, universal=None, default=True),
      arch_map=arch_map)

  def build_fn(self, system, wheel):
    if wheel.plat.name in self._packaged:
      return BuildPackageFromPyPiWheel(system, wheel)

    dx = system.dockcross_image(wheel.plat)
    assert dx, 'Docker image required for compilation.'
    with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
      # Unpack "cryptography".
      crypt_dir = system.repo.ensure(self._crypt_src, tdir)

      # Unpack "OpenSSL" into the "openssl/" subdirectory.
      openssl_dir = system.repo.ensure(self._openssl_src, tdir)

      # Build OpenSSL. We build this out of "openssl_dir" and install to
      # <openssl_dir>/PREFIX, so that will be the on-disk path to our OpenSSL
      # libraries.
      #
      # "Configure" must be run in the directory in which it builds, so we
      # `cd` into "openssl_dir" using dockcross "run_args".
      prefix = dx.workrel(tdir, tdir, 'prefix')
      util.check_run_script(
          system,
          dx,
          tdir,
          [
            '#!/bin/bash',
            'set -e',
            'export NUM_CPU="$(getconf _NPROCESSORS_ONLN)"',
            'echo "Using ${NUM_CPU} CPU(s)"',
            ' '.join([
              './Configure',
              '-fPIC',
              '--prefix=%s' % (prefix,),
              'no-shared',
              'no-afalgeng',  # https://github.com/openssl/openssl/issues/1685
              'no-ssl3',
              wheel.plat.openssl_target,
            ]),
            'make -j${NUM_CPU}',
            'make install',
          ],
          cwd=openssl_dir,
      )

      # Build "cryptography".
      d = {
        'prefix': prefix,
      }
      util.check_run_script(
          system,
          dx,
          tdir,
          [
            '#!/bin/bash',
            'set -e',
            'export CFLAGS="' + ' '.join([
              '-I%(prefix)s/include' % d,
              '$CFLAGS',
            ]) + '"',
            'export LDFLAGS="' + ' '.join([
              '-L%(prefix)s/lib' % d,
              '-L%(prefix)s/lib64' % d,
              '$LDFLAGS',
            ]) + '"',
            ' '.join([
              'python2.7',
              'setup.py',
              'build_ext',
              '--include-dirs', '/usr/cross/include',
              '--library-dirs', '/usr/cross/lib',
              '--force', 'build',
              '--force', 'build_scripts',
              '--executable=/usr/local/bin/python',
              '--force', 'bdist_wheel',
              '--plat-name', wheel.primary_platform,
            ]),
          ],
          cwd=crypt_dir,
      )

      StageWheelForPackage(
        system, os.path.join(crypt_dir, 'dist'), wheel)
      return None


class CryptographyPyPI(Cryptography):
  def __init__(self, name, ver, openssl):
    """Adapts Cryptography wheel builder to use available PyPI wheels.

    Builds wheels for platforms not present in PyPI (e.g ARM) from source.
    Builds statically and links to OpenSSL of given version.
    """
    super(CryptographyPyPI, self).__init__(name,
      source.pypi_sdist('cryptography', ver),
      source.remote_archive(
          name='openssl',
          version=openssl,
          url='https://www.openssl.org/source/openssl-%s.tar.gz' % openssl,
      ),
      arch_map={
        'mac-x64': ['macosx_10_6_intel'],
      },
      packaged=[
        'manylinux-x86',
        'manylinux-x64',
        'mac-x64',
        'windows-x86',
        'windows-x64',
      ],
  )
