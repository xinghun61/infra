# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api


REPO_URL = (
  'https://chromium.googlesource.com/external/github.com/ninja-build/ninja')
PACKAGE_PREFIX = 'infra/ninja/'

# This version suffix serves to distinguish different revisions of Ninja built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''

class NinjaApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self, platform_name=None, platform_bits=None):
    platform_name = platform_name or self.m.platform.name
    platform_bits = platform_bits or self.m.platform.bits

    workdir = self.m.path['start_dir'].join('ninja')
    self.m.file.rmtree('rmtree workdir', workdir)

    env_prefixes = {}
    if self.m.platform.is_win:
      cipddir = workdir.join('_cipd')
      self.m.cipd.ensure(cipddir, {
        'chrome_internal/third_party/sdk/windows': 'uploaded:2018-06-13',
      })

      filename = 'SetEnv.%s.json' % {32: 'x86', 64: 'x64'}[platform_bits]
      step_result = self.m.json.read(
          'read %s' % filename, cipddir.join('win_sdk', 'bin', filename),
          step_test_data=lambda: self.m.json.test_api.output({
              'env': {'PATH': [['..', '..', 'win_sdk', 'bin', 'x64']]},
          }))
      for k, v in step_result.json.output['env'].iteritems():
        env_prefixes[k] = ['%s' % cipddir.join(*p[2:]) for p in v]

    def install(target_dir, _tag):
      with self.m.context(env_prefixes=env_prefixes):
        self.m.python('bootstrap',
                      workdir.join('checkout', 'configure.py'),
                      ['--bootstrap'])
      ninja = 'ninja' + ('.exe' if self.m.platform.is_win else '')
      self.m.file.copy(
        'install ninja', workdir.join('checkout', ninja), target_dir)

    tag = self.m.properties.get('ninja_release_tag')
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
