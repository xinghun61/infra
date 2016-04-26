# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe to build windows depot_tools bootstrap zipfile."""

DEPS = [
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',

  'depot_tools/git',
  'depot_tools/infra_paths',

  'file',
  'gsutil',
  'zip',
]

from recipe_engine.recipe_api import Property

REPO_URL='https://chromium.googlesource.com/chromium/tools/depot_tools.git'
DOC_UPLOAD_URL='gs://chrome-infra-docs/flat/depot_tools/docs/'

PROPERTIES = {
  'revision': Property(
    kind=str, help='The revision of depot_tools to check out'),
}

def RunSteps(api, revision):
  # prepare the output dir and zip paths
  api.path['checkout'] = api.infra_paths['slave_build'].join('depot_tools')
  zip_out = api.infra_paths['slave_build'].join('depot_tools.zip')

  with api.step.nest('clean workspace'):
    api.file.rmtree('rm depot_tools', api.path['checkout'])
    api.file.remove('rm depot_tools.zip', zip_out, ok_ret=(0, 1))

    # generate the new directory
    api.step('mk depot_tools', ['mkdir', api.path['checkout']])

  with api.step.nest('clone + checkout'):
    api.git('clone', '--single-branch', '-n', REPO_URL, api.path['checkout'])
    api.git('config', 'core.autocrlf', 'false', name='set autocrlf')
    api.git('config', 'core.filemode', 'false', name='set filemode')
    api.git('config', 'core.symlinks', 'false', name='set symlinks')
    api.git('checkout', 'origin/master')
    api.git('reset', '--hard',  revision)
    api.git('reflog', 'expire', '--all')
    api.git('gc', '--aggressive', '--prune=all')

  # zip + upload repo
  api.zip.directory('zip it up', api.path['checkout'], zip_out)
  api.gsutil.upload(zip_out, 'chrome-infra', 'depot_tools.zip',
                    args=['-a', 'public-read'], unauthenticated_url=True)

  # upload html docs
  api.gsutil(['cp', '-r', '-z', 'html', '-a', 'public-read',
              api.path['checkout'].join('man', 'html'), DOC_UPLOAD_URL],
             name='upload docs')


def GenTests(api):
  yield api.test('basic') + api.properties(revision='deadbeef')
