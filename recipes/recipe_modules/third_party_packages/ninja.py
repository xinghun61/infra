# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api


REPO_URL = (
  'https://chromium.googlesource.com/external/github.com/ninja-build/ninja')
PACKAGE_PREFIX = 'infra/ninja/'

# This version suffix serves to distinguish different revisions of git built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''

class NinjaApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    if self.m.platform.is_win:
      self.m.python.succeeding_step('Windows Not Supported', 'Maybe later.')
      return

    workdir = self.m.path['start_dir'].join('ninja')
    self.m.file.rmtree('rmtree workdir', workdir)

    def install(target_dir, _tag):
      self.m.python('bootstrap',
                    workdir.join('checkout', 'configure.py'), ['--bootstrap'])
      ninja = 'ninja' + ('.exe' if self.m.platform.is_win else '')
      self.m.file.copy(
        'install ninja', workdir.join('checkout', ninja), target_dir)

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
