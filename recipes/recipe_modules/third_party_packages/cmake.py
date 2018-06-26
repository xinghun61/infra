# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api


REPO_URL = (
  'https://chromium.googlesource.com/external/github.com/Kitware/CMake')
PACKAGE_PREFIX = 'infra/cmake/'

# This version suffix serves to distinguish different revisions of CMake built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''

class CMakeApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self, platform_name=None, platform_bits=None):
    platform_name = platform_name or self.m.platform.name
    platform_bits = platform_bits or self.m.platform.bits

    if platform_name == 'win' and platform_bits == 32:
      self.m.step('32-bit Windows build is not supported', cmd=None)
      return

    # TODO: Remove this conditional when the same bootstrap version exists for
    # all platforms.
    bootstrap_cmake_version_tag = 'version:3.11.4'
    if platform_name == 'mac' and platform_bits == 64:
      # The "version:3.11.4" package doesn't exist for the "mac-amd64".
      bootstrap_cmake_version_tag = 'version:3.11.3'

    workdir = self.m.path['start_dir'].join('cmake')
    self.m.file.rmtree('rmtree workdir', workdir)

    cipddir = workdir.join('_cipd')
    packages = {
      'infra/ninja/${platform}': 'version:1.8.2',
      'infra/cmake/${platform}': bootstrap_cmake_version_tag,
    }
    self.m.cipd.ensure(cipddir, packages)

    def install(target_dir, _tag):
      src_dir = self.m.context.cwd

      build_dir= workdir.join('build')
      self.m.file.ensure_directory('build_dir', build_dir)

      with self.m.context(cwd=build_dir):
        with self.m.windows_sdk(enabled=self.m.platform.is_win):
          self.m.step('configure cmake', [
            cipddir.join('bin', 'cmake'),
            '-GNinja',
            '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_INSTALL_PREFIX=',
            '-DCMAKE_MAKE_PROGRAM=%s' % cipddir.join('ninja'),
            '-DCMAKE_USE_OPENSSL=OFF',
            src_dir,
          ])
          self.m.step('build cmake', [cipddir.join('ninja')])
          with self.m.context(env={'DESTDIR': target_dir}):
            self.m.step('install cmake', [cipddir.join('ninja'), 'install'])

    tag = self.m.properties.get('cmake_release_tag')
    if not tag:
      tag = self.get_latest_release_tag(REPO_URL, 'v')
    version = tag.lstrip('v') + PACKAGE_VERSION_SUFFIX
    self.ensure_package(
        workdir,
        REPO_URL,
        PACKAGE_PREFIX,
        install,
        tag,
        version,
        'copy',
    )
