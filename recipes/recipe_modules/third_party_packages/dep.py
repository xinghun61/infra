# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api


REPO_URL = (
  'https://chromium.googlesource.com/external/github.com/golang/dep')
PACKAGE_PREFIX = 'go/cmd/github.com/golang/dep/'

# This version suffix serves to distinguish different revisions of git built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''

class DepApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    tag = self.m.properties.get('git_release_tag')
    if not tag:
      tag = self.get_latest_release_tag(REPO_URL, 'v')
    version = tag.lstrip('v') + PACKAGE_VERSION_SUFFIX

    package_name = self.get_package_name(PACKAGE_PREFIX)

    # Check if the package already exists.
    if self.does_package_exist(package_name, version):
      self.m.python.succeeding_step('Synced', 'Package is up to date.')
      return

    workdir = self.m.path['start_dir'].join('dep')
    self.m.file.rmtree('rmtree workdir', workdir)

    srcdir = workdir.join('src')
    bindir = workdir.join('bin')

    # Fetch source code and build.
    self.m.git.checkout(
        REPO_URL, ref='refs/tags/' + tag,
        dir_path=srcdir.join('github.com', 'golang', 'dep'),
        submodules=False)

    cipddir = workdir.join('_cipd')
    self.m.cipd.ensure(cipddir, {
      'infra/go/${platform}': 'version:1.9.4',
    })

    goenv = {
        'GOROOT': cipddir,
        'GOPATH': workdir,
        'GOBIN': bindir,
    }

    with self.m.context(env=goenv):
      self.m.step('go get', [
        cipddir.join('bin', 'go'),
        'get', 'github.com/golang/dep/cmd/dep'
      ])

    package_file = self.build_package(
        package_name,
        workdir,
        bindir,
        'symlink'
    )

    self.register_package(package_file, package_name, version)
