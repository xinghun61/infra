# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe to build windows depot_tools bootstrap zipfile."""

DEPS = [
  'build/zip',
  'depot_tools/cipd',
  'depot_tools/git',
  'depot_tools/gsutil',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/tempfile',
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
  api.path['checkout'] = api.path['start_dir'].join('depot_tools')
  zip_out = api.path['start_dir'].join('depot_tools.zip')

  with api.step.nest('clean workspace'):
    api.file.rmtree('rm depot_tools', api.path['checkout'])
    api.file.remove('rm depot_tools.zip', zip_out)

    # generate the new directory
    api.step('mk depot_tools', ['mkdir', api.path['checkout']])

  with api.step.nest('clone + checkout'):
    api.git('clone', '--single-branch', '-n', REPO_URL, api.path['checkout'])
    api.step.active_result.presentation.properties['got_revision'] = revision
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

  # upload git cipd package


  # TODO(crbug.com/638337): cipd module doesn't allow `create` to work in this
  # way.
  def create(pkg_dir, step_title, platform, refs=()):
    """Pushes given package directory up to CIPD with provided refs."""
    cmd = [
      'cipd',
      'create',
      '-in', pkg_dir,
      '-name', 'infra/depot_tools/git_installer/%s' % platform,
      '-service-account-json',
      api.cipd.default_bot_service_account_credentials,
    ]
    for r in refs:
      cmd += ['-ref', r]
    api.step('create installer package (%s)' % step_title, cmd)

  def pull_and_upload(version, step_title, refs=()):
    """Pulls given version from google storage, then pushes it up to CIPD.

    Sets package refs to the provided ones, plus an additional ref of the
    specific version number provided (prepended with 'v' and with '.'s replaced
    with '_'). So version=='2.8.3' will create a ref 'v2_8_3'.

    version (str) - A version string for one of the git installers in
      gs://chrome-infra, like '2.8.3'.
    """
    refs = ['v' + version.replace('.', '_')] + refs
    with api.tempfile.temp_dir('git_installer') as git_cipd_dir:
      outfile = git_cipd_dir.join('git-installer.exe')

      api.gsutil.download(
        'chrome-infra', 'PortableGit-%s-64-bit.7z.exe' % version, outfile,
        name='fetch 64-bit git installer (v%s)' % version)
      create(git_cipd_dir, step_title, 'windows-amd64', refs)

      api.gsutil.download(
        'chrome-infra', 'PortableGit-%s-32-bit.7z.exe' % version, outfile,
        name='fetch 32-bit git installer (v%s)' % version)
      create(git_cipd_dir, step_title, 'windows-386', refs)


  bs_win = api.path['checkout'].join('bootstrap', 'win')

  version = api.file.read_text(
    'read git version', bs_win.join('git_version.txt'),
    test_data='1.2.3\n').strip()
  api.step.active_result.presentation.step_text = 'got %r' % version

  bleeding_edge = api.file.read_text('read git version (bleeding_edge)',
    bs_win.join('git_version_bleeding_edge.txt'), test_data='2.2.3\n').strip()
  api.step.active_result.presentation.step_text = 'got %r' % bleeding_edge

  if version == bleeding_edge:
    pull_and_upload(version, 'normal and bleeding_edge',
                    ['latest', 'bleeding_edge'])
  else:
    pull_and_upload(version, 'normal', ['latest'])
    pull_and_upload(bleeding_edge, 'bleeding_edge', ['bleeding_edge'])


def GenTests(api):
  yield (
      api.test('basic') +
      api.properties(path_config='kitchen', revision='deadbeef')
  )

  yield (
    api.test('identical_normal_bleeding_edge_git_versions') +
    api.properties(path_config='kitchen', revision='deadbeef') +
    api.step_data('read git version', api.raw_io.output_text('2.2.3'))
  )
