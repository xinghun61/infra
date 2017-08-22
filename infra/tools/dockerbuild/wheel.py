# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Manages the generation and uploading of Python wheel CIPD packages."""

import collections
import itertools
import os
import shutil
import sys
import tempfile

from . import cipd
from . import source
from . import platform
from . import util


UniversalSpec = collections.namedtuple('UniversalSpec', (
    'pyversions'))


_Spec = collections.namedtuple('_Spec', (
    'name', 'version', 'universal'))
class Spec(_Spec):

  @property
  def tuple(self):
    return (self.name, self.version)

  @property
  def tag(self):
    return '%s-%s' % (self.name, self.version)


_Wheel = collections.namedtuple('_Wheel', (
    'spec', 'plat', 'pyversion', 'filename'))
class Wheel(_Wheel):

  @property
  def pyversion_str(self):
    if self.spec.universal:
      pyv = self.spec.universal.pyversions
      if pyv is None:
        return 'py2.py3'
      assert 'py2' in pyv
      return 'py2'
    return 'cp%s' % (self.pyversion,)

  @property
  def abi(self):
    if self.spec.universal or not self.plat.wheel_abi:
      return 'none'
    return self.plat.wheel_abi

  @property
  def platform(self):
    return 'any' if self.spec.universal else self.plat.wheel_plat

  def default_filename(self):
    d = {
        'name': self.spec.name.replace('-', '_'),
        'version': self.spec.version,
        'pyversion': self.pyversion_str,
        'abi': self.abi,
        'platform': self.platform,
    }
    return '%(name)s-%(version)s-%(pyversion)s-%(abi)s-%(platform)s.whl' % d

  def path(self, system):
    return os.path.join(system.wheel_dir, self.filename)

  @property
  def cipd_package(self):
    base_path = ('infra', 'python', 'wheels')
    if self.spec.universal:
      base_path += ('%s-%s' % (self.spec.name, self.pyversion_str),)
    else:
      base_path += (
          self.spec.name,
          '%s_%s_%s' % (self.plat.cipd_platform, self.pyversion_str, self.abi),
      )

    tags = [
      'version:%s' % (self.spec.version,),
    ]
    return cipd.Package(
      name=('/'.join(p.replace('.', '_') for p in base_path)).lower(),
      tags=tuple(tags),
      install_mode=cipd.INSTALL_SYMLINK,
      compress_level=cipd.COMPRESS_NONE,
    )


class PlatformNotSupported(Exception):
  """Exception raised by Builder.build when the specified wheel's platform is
  not support."""


class Builder(object):

  def __init__(self, spec, build_fn, arch_map=None, abi_map=None,
               only_plat=None, skip_plat=None):
    self._spec = spec
    self._build_fn = build_fn
    self._arch_map = arch_map or {}
    self._abi_map = abi_map or {}
    self._only_plat = frozenset(only_plat or ())
    self._skip_plat = frozenset(skip_plat or ())

  @property
  def spec(self):
    return self._spec

  def wheel(self, _system, plat):
    wheel = Wheel(
        spec=self._spec,
        plat=plat,
        # Only support Python 2.7 for now, can augment later.
        pyversion='27',
        filename=None)

    # Determine our package's wheel filename. This incorporates "abi" and "arch"
    # override maps, which are a priori knowledge of the package repository's
    # layout. This can differ from the local platform value if the package was
    # valid and built for multiple platforms, which seems to happen on Mac a
    # lot.
    return wheel._replace(
        filename=wheel._replace(
          plat=wheel.plat._replace(
            wheel_abi=self._abi_map.get(plat.name, plat.wheel_abi),
            wheel_plat=self._arch_map.get(plat.name, plat.wheel_plat),
          ),
        ).default_filename(),
    )

  def build(self, wheel, system, rebuild=False):
    if self._only_plat and wheel.plat.name not in self._only_plat:
      raise PlatformNotSupported()
    if wheel.plat.name in self._skip_plat:
      raise PlatformNotSupported()

    pkg_path = os.path.join(system.pkg_dir, '%s.pkg' % (wheel.filename,))
    if not rebuild and os.path.isfile(pkg_path):
      util.LOGGER.info('Package is already built: %s', pkg_path)
      return pkg_path

    # Rebuild the wheel, if necessary.
    wheel_path = wheel.path(system)
    if rebuild or not os.path.isfile(wheel_path):
      self._build_fn(system, wheel)
    else:
      util.LOGGER.info('Wheel is already built: %s', wheel_path)

    # Create a CIPD package for the wheel.
    util.LOGGER.info('Creating CIPD package: %r => %r', wheel_path, pkg_path)
    with system.temp_subdir('cipd_%s_%s' % wheel.spec.tuple) as tdir:
      shutil.copy(wheel_path, tdir)
      system.cipd.create_package(wheel.cipd_package, tdir, pkg_path)

    return pkg_path


def check_run(system, dx, work_root, cmd, cwd=None):
  """Runs a command |cmd|.

  Args:
    system (runtime.System): The System instance.
    dx (dockcross.Image or None): The DockCross image to use. If None, the
        command will be run on the local system.
    work_root (str): The work root directory. If |dx| is not None, this will
        be the directory mounted as "/work" in the Docker environment.
    cmd (list): The command to run. Any components that are paths beginning
        with |work_root| will be automatically made relative to |work_root|.
    cwd (str or None): The working directory for the command. If None,
        |work_root| will be used. Otherwise, |cwd| must be a subdirectory of
        |work_root|.
    """
  if dx is None:
    return system.check_run(cmd, cwd=cwd or work_root)
  return dx.check_run(work_root, cmd, cwd=cwd)


def check_run_script(system, dx, work_root, script, args=None, cwd=None):
  """Runs a script, |script|.

  An anonymous file will be created under |work_root| holding the specified
  script.

  Args:
    script (list): A list of script lines to execute.
    See "check_run" for full argument definition.
  """
  with util.anonfile(work_root, text=True) as fd:
    for line in script:
      fd.write(line)
      fd.write('\n')
  os.chmod(fd.name, 0755)

  util.LOGGER.debug('Running script (path=%s): %s', fd.name, script)
  cmd = [fd.name]
  if args:
    cmd.extend(args)
  return check_run(system, dx, work_root, cmd, cwd=cwd)


def _build_package(system, wheel):
  with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
    check_run(
        system,
        None,
        tdir,
        [
          'pip',
          'download',
          '--no-deps',
          '--only-binary=:all:',
          '--abi=%s' % (wheel.abi,),
          '--python-version=%s' % (wheel.pyversion,),
          '--platform=%s' % (wheel.platform,),
          '%s==%s' % (wheel.spec.name, wheel.spec.version),
        ],
        cwd=tdir)
    wheel_path = os.path.join(tdir, wheel.filename)
    shutil.copy(wheel_path, system.wheel_dir)


def _build_source(system, wheel, src, universal=False):
  dx = system.dockcross_image(wheel.plat)
  with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
    build_dir = system.repo.ensure(src, tdir)

    bdist_wheel_opts = []
    if universal:
      bdist_wheel_opts.append('--universal')
    else:
      bdist_wheel_opts.append('--plat-name=%s' % (wheel.plat.wheel_plat,))

    cmd = [
      'pip',
      'wheel',
      '--no-deps',
      '--only-binary=:all:',
      '--wheel-dir', tdir,
    ]
    for opt in bdist_wheel_opts:
      cmd += ['--build-option', opt]
    cmd.append('.')

    check_run(
        system,
        dx,
        tdir, 
        cmd,
        cwd=build_dir)

    wheel_path = os.path.join(tdir, wheel.filename)
    shutil.copy(wheel_path, system.wheel_dir)


def _build_cryptography(system, wheel, src, openssl_src):
  dx = system.dockcross_image(wheel.plat)
  assert dx, 'Docker image required for compilation.'
  with system.temp_subdir('%s_%s' % wheel.spec.tuple) as tdir:
    # Unpack "cryptography".
    crypt_dir = system.repo.ensure(src, tdir)

    # Unpack "OpenSSL" into the "openssl/" subdirectory.
    openssl_dir = system.repo.ensure(openssl_src, tdir)

    # Build OpenSSL. We build this out of "openssl_dir" and install to
    # <openssl_dir>/PREFIX, so that will be the on-disk path to our OpenSSL
    # libraries.
    #
    # "Configure" must be run in the directory in which it builds, so we
    # `cd` into "openssl_dir" using dockcross "run_args".
    prefix = dx.workpath('prefix')
    check_run_script(
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
    check_run_script(
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
            '--force', 'bdist_wheel', '--plat-name', wheel.plat.wheel_plat,
          ]),
        ],
        cwd=crypt_dir,
    )

    wheel_path = os.path.join(crypt_dir, 'dist', wheel.filename)
    shutil.copy(wheel_path, system.wheel_dir)


def BuildWheel(name, version, **kwargs):
  pypi_src = source.pypi_sdist(name, version)
  spec = Spec(name=name, version=pypi_src.version, universal=None)

  packaged = set(kwargs.pop('packaged', (p.name for p in platform.PACKAGED)))

  def build_fn(system, wheel):
    if wheel.plat.name in packaged:
      return _build_package(system, wheel)
    return _build_source(system, wheel, pypi_src)

  return Builder(spec, build_fn, **kwargs)


def BuildCryptographyWheel(name, crypt_src, openssl_src, packaged=None):
  spec = Spec(name=name, version=crypt_src.version, universal=None)

  def build_fn(system, wheel):
    if wheel.plat.name in (packaged or ()):
      return _build_package(system, wheel)
    return _build_cryptography(system, wheel, crypt_src, openssl_src)

  return Builder(spec, build_fn)


def Packaged(name, version, only_plat, **kwargs):
  spec = Spec(
      name=name,
      version=version,
      universal=None,
  )

  def build_fn(system, wheel):
    return _build_package(system, wheel)

  kwargs['only_plat'] = only_plat
  return Builder(spec, build_fn, **kwargs)


def Universal(name, version, pyversions=None, **kwargs):
  spec = Spec(
      name=name,
      version=version,
      universal=UniversalSpec(
        pyversions=pyversions,
      ),
  )

  return Builder(spec, _build_package, **kwargs)


def UniversalSource(name, pypi_version, pyversions=None, pypi_name=None,
                    **kwargs):
  pypi_src = source.pypi_sdist(
      name=pypi_name or name,
      version=pypi_version)

  spec = Spec(
      name=name,
      version=pypi_src.version,
      universal=UniversalSpec(
        pyversions=pyversions,
      ),
  )

  def build_fn(system, wheel):
    return _build_source(system, wheel, pypi_src, universal=True)

  return Builder(spec, build_fn, **kwargs)


SPECS = {s.spec.tag: s for s in (
  BuildWheel('coverage', '4.3.4'),
  BuildWheel('cffi', '1.10.0',
    arch_map={
      'mac-x64': 'macosx_10_6_intel',
    },
  ),
  BuildWheel('numpy', '1.12.1',
      abi_map={
        'windows-x86': 'none',
        'windows-x64': 'none',
      },
      arch_map={
        'mac-x64': '.'.join([
          'macosx_10_6_intel',
          'macosx_10_9_intel',
          'macosx_10_9_x86_64',
          'macosx_10_10_intel',
          'macosx_10_10_x86_64',
        ]),
      },
      skip_plat=('linux-arm64',),
  ),

  BuildWheel('psutil', '5.2.2',
      abi_map={
        'windows-x86': 'none',
        'windows-x64': 'none',
      },
      arch_map={
        'mac-x64': '.'.join([
          'macosx_10_6_intel',
          'macosx_10_9_intel',
          'macosx_10_9_x86_64',
          'macosx_10_10_intel',
          'macosx_10_10_x86_64',
        ]),
      },
      packaged=['windows-x86', 'windows-x64'],
  ),

  Packaged('scipy', '0.19.0',
      ['mac-x64', 'manylinux-x86', 'manylinux-x64'],
      arch_map={
        'mac-x64': '.'.join([
          'macosx_10_6_intel',
          'macosx_10_9_intel',
          'macosx_10_9_x86_64',
          'macosx_10_10_intel',
          'macosx_10_10_x86_64',
        ]),
      },
  ),

  Packaged('opencv_python', '3.2.0.7',
      [
        'mac-x64',
        'manylinux-x86',
        'manylinux-x64',
        'windows-x86',
        'windows-x64',
      ],
      arch_map={
        'mac-x64': '.'.join([
          'macosx_10_6_intel',
          'macosx_10_9_intel',
          'macosx_10_9_x86_64',
          'macosx_10_10_intel',
          'macosx_10_10_x86_64',
        ]),
      },
  ),

  BuildCryptographyWheel('cryptography',
      source.pypi_sdist('cryptography', '1.8.1'),
      source.remote_archive(
          name='openssl',
          version='1.1.0e',
          url='https://www.openssl.org/source/openssl-1.1.0e.tar.gz',
      ),
      packaged=[
        'mac-x64',
        'windows-x86',
        'windows-x64',
      ],
  ),

  BuildWheel('crcmod', '1.7', packaged=()),
  BuildWheel('grpcio', '1.4.0'),
  BuildWheel('scan-build', '2.0.8'),

  Universal('appdirs', '1.4.3'),
  UniversalSource('Appium_Python_Client', '0.24',
                   pypi_name='Appium-Python-Client'),
  Universal('asn1crypto', '0.22.0'),
  Universal('astunparse', '1.5.0'),
  Universal('Django', '1.9'),
  Universal('enum34', '1.1.6', pyversions=['py2', 'py3']),
  Universal('funcsigs', '1.0.2'),
  Universal('google_api_python_client', '1.6.2'),
  UniversalSource('apache-beam', '2.0.0'),
  UniversalSource('httplib2', '0.10.3'),
  Universal('idna', '2.5'),
  Universal('ipaddress', '1.0.18', pyversions=['py2']),
  Universal('mock', '2.0.0'),
  Universal('oauth2client', '4.0.0'),
  Universal('packaging', '16.8'),
  Universal('pbr', '3.0.0'),
  Universal('protobuf', '3.2.0'),
  Universal('pyasn1', '0.2.3'),
  Universal('pyasn1_modules', '0.0.8'),
  UniversalSource('pycparser', '2.17'),
  Universal('pyopenssl', '17.0.0'),
  Universal('pyparsing', '2.2.0'),
  Universal('requests', '2.13.0'),
  Universal('rsa', '3.4.2'),
  Universal('selenium', '3.4.1'),
  Universal('setuptools', '34.3.2'),
  Universal('six', '1.10.0'),
  Universal('uritemplate', '3.0.0'),
)}
SPEC_NAMES = sorted(SPECS.keys())
