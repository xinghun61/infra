# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api


REPO_URL = (
  'https://chromium.googlesource.com/external/github.com/swig/swig')
PACKAGE_PREFIX = 'infra/swig/'

# This version suffix serves to distinguish different revisions of git built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''

class SwigApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    if self.m.platform.is_win:
      self.m.python.succeeding_step('Windows not supported', 'Maybe later.')
      return

    workdir = self.m.path['start_dir'].join('swig')
    support = self.support_prefix(workdir.join('_support'))
    self.m.file.rmtree('rmtree workdir', workdir)

    def install(target_dir, _tag):
      patches = [self.resource('swig', 'patches').join(x) for x in (
          '0001-Use-relative-path-to-swiglib-on-Darwin-and-Linux.patch',
      )]
      self.m.git(*[
          '-c', 'user.name=third_party_packages',
          '-c', 'user.email=third_party_packages@example.com',
          'am'] + patches,
          name='git apply patches')

      autoconf = support.ensure_autoconf()
      automake = support.ensure_automake()
      env_prefixes = {
          'PATH': [autoconf.bin_dir, automake.bin_dir],
      }

      with self.m.context(env_prefixes=env_prefixes):
        self.m.step('autogen', ['./autogen.sh'])
        self.m.step('configure', [
          './configure',
          '--prefix=',
        ])
        self.m.step('make', ['make'])
        with self.m.context(env={'DESTDIR': target_dir}):
          self.m.step('make install', ['make', 'install'])

    tag = self.m.properties.get('git_release_tag')
    if not tag:
      tag = self.get_latest_release_tag(REPO_URL, 'rel-')
    version = tag.lstrip('rel-') + PACKAGE_VERSION_SUFFIX
    self.ensure_package(
        workdir,
        REPO_URL,
        PACKAGE_PREFIX,
        install,
        tag,
        version,
        'symlink',
    )
