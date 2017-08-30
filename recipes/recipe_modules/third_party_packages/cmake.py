# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api


REPO_URL = (
  'https://chromium.googlesource.com/external/github.com/Kitware/CMake')
PACKAGE_PREFIX = 'infra/cmake/'

# This version suffix serves to distinguish different revisions of git built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''

class CMakeApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    if self.m.platform.is_win:
      # TODO(phosek): To build CMake on Windows, we need a CMake (and Ninja)
      # which is a chicken and egg problem. To solve that problem, someone
      # will have to manually build and upload CMake package for Windows.
      self.m.python.succeeding_step('Windows not supported', 'Maybe later.')
      return

    workdir = self.m.path['start_dir'].join('cmake')
    self.m.file.rmtree('rmtree workdir', workdir)

    def install(target_dir, _tag):
      src_dir = self.m.context.cwd

      bootstrap_dir= workdir.join('bootstrap')
      self.m.file.ensure_directory('bootstrap_dir', bootstrap_dir)

      with self.m.context(cwd=bootstrap_dir):
        self.m.step('bootstrap cmake', [src_dir.join('bootstrap')])
        self.m.step('make cmake', ['make'])

      cipddir = workdir.join('_cipd')
      self.m.cipd.ensure(cipddir, {
        'infra/ninja/${platform}': 'version:1.7.2',
      })

      build_dir= workdir.join('build')
      self.m.file.ensure_directory('build_dir', build_dir)

      with self.m.context(cwd=build_dir):
        self.m.step('configure cmake', [
          bootstrap_dir.join('bin', 'cmake'),
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

    tag = self.m.properties.get('git_release_tag')
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
        'symlink',
    )
