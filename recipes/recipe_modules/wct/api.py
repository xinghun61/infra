# Copyright 2016 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

from recipe_engine import recipe_api
import os

class WCTApi(recipe_api.RecipeApi):
  """WCTApi provides support for running Web Component Tests"""

  def __init__(self, *args, **kwargs):
    super(WCTApi, self).__init__(*args, **kwargs)

  def install(self):
    cipd_root = self.m.path['start_dir'].join('packages')
    wct_package_name = 'infra/testing/wct/%s' % self.m.cipd.platform_suffix()
    node_package_name = ('infra/nodejs/nodejs/%s' %
        self.m.cipd.platform_suffix())
    chrome_package_name = ('dart/browsers/chrome/%s' %
        self.m.cipd.platform_suffix())

    packages = {
      wct_package_name: 'prod',
      node_package_name: 'node_version:4.5.0',
      chrome_package_name: 'b6b434ed592da55513d813b2cfb3422008fb280d',
    }
    self.m.cipd.ensure(cipd_root, packages)

  def run(self, root, prefix='test/', step_name='Run WCT tests'):
    if not self.m.platform.is_linux:
      raise recipe_api.StepFailure('WCT only runs on Linux.')

    wct_root = self.m.path['start_dir'].join('packages')
    node_path = self.m.path['start_dir'].join('packages', 'bin')
    chrome_bin = self.m.path['start_dir'].join('packages', 'chrome', 'chrome')

    env = {
      'PATH': self.m.path.pathsep.join([str(node_path), '%(PATH)s'])
    }

    wct_bin = wct_root.join('wct')

    with self.m.context(env=env):
      self.m.step('Print chrome version', [chrome_bin, '--version'])

    if self.m.path.exists(self.m.path.join(root, 'package.json')):
        with self.m.context(env=env, cwd=root):
          self.m.step('Install node modules', [node_path.join('npm'), 'install',
              '--no-save'])

    with self.m.context(env=env):
      self.m.step('Install bower', [node_path.join('npm'), 'install', '-g',
          'bower'])
    with self.m.context(env=env, cwd=root):
      self.m.step('Install bower packages', ['bower', 'install'])
    with self.m.context(env=env, cwd=root):
      self.m.step(step_name, ['xvfb-run', '-a', wct_bin, '--base', root,
          '--chrome', chrome_bin, '--prefix', prefix])
