# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import re

from recipe_engine.recipe_api import Property

DEPS = [
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/gitiles',
]

PROPERTIES = {
    'source_repo': Property(
        help='The URL of the repo to be mirrored with submodules'),
    'target_repo': Property(
        help='The URL of the mirror repo to be built/maintained'),
}

COMMIT_USERNAME = 'Submodules bot'

def RunSteps(api, source_repo, target_repo):
  _, source_project = api.gitiles.parse_repo_url(source_repo)
  target_host, target_project = api.gitiles.parse_repo_url(target_repo)
  # This must be on googlesource.com, as we depend on the _direct endpoint for
  # force pushed.
  assert target_host.endswith('googlesource.com')

  checkout_dir = api.m.path['cache'].join(
      re.sub(r'\W', '_', api.buildbucket.builder_name))
  api.m.file.ensure_directory('Create checkout parent dir', checkout_dir)

  source_checkout_name = source_project[source_project.rfind('/') + 1:] + '/'
  source_checkout_dir = checkout_dir.join(source_checkout_name)

  # TODO: less hacky way of checking if the dir exists?
  glob = api.m.file.glob_paths('Check for existing source checkout dir',
                               checkout_dir, source_checkout_name)
  if glob == []:
    api.git('checkout', source_repo, source_checkout_dir)

  # This is implicitly used by all the git steps below.
  api.m.path['checkout'] = source_checkout_dir

  # This will do a force update, removing any synthetic commits we may have.
  api.git('fetch', '--all')

  with api.step.nest('Check for new commits') as step:
    commits, _ = api.gitiles.log(target_repo, 'master', limit=2,
                                 step_name='Find latest commit to target repo')
    if commits != [] and commits[0]['author']['name'] == COMMIT_USERNAME:
      latest_real_commit_in_target = commits[1]['commit']
      latest_commit_in_source = api.git(
          'rev-parse', 'master',
          stdout=api.raw_io.output(),
          name='Get latest commit hash in source repo').stdout.strip()
      if latest_real_commit_in_target == latest_commit_in_source:
        step.presentation.step_text = 'no new commits, exiting'
        return

      # If we get here we'll need to generate a new commit. We don't care
      # whether DEPS has changed, since we always want to include the latest
      # commit in the target repo.
    else:
      # HEAD in the target repo isn't authored by the submodules bot. This means
      # we definitely need to generate a new commit. Either we've never run on
      # this repo or we somehow ended up in an invalid state.
      pass

  gclient_spec = ("solutions=[{"
                  "'managed':False,"
                  "'name':'%s',"
                  "'url':'%s',"
                  "'deps_file':'DEPS'}]"
                  % (source_checkout_name, source_repo))
  with api.context(cwd=source_checkout_dir):
    deps = json.loads(api.gclient('evaluate DEPS',
                                  ['revinfo', '--deps', '--all',
                                   '--ignore-dep-type=cipd',
                                   '--spec', gclient_spec, '--output-json=-'],
                                  stdout=api.raw_io.output_text()).stdout)

  gitmodules_entries = []
  # The "api.git" call below generates a step. This will be executed once per
  # entry in DEPS, so we tuck it away inside this parent step to make the
  # resulting list of executed steps more readable.
  with api.step.nest('Add gitlinks'):
    for path, entry in deps.iteritems():
      if not path.startswith(source_checkout_name):
        continue
      path = str(path[len(source_checkout_name):])

      gitmodules_entries.append('[submodule "%s"]\n\tpath = %s\n\turl = %s'
                                % (path, path, str(entry['url'])))
      # This adds a submodule entry to the index without cloning the underlying
      # repository.
      api.git('update-index', '--add', '--cacheinfo', '160000', entry['rev'],
              path, name='Add %s gitlink' % path)

  api.file.write_text('Write .gitmodules file',
                      source_checkout_dir.join('.gitmodules'),
                      '\n'.join(gitmodules_entries))
  api.git('add', '.gitmodules')

  api.git('-c', 'user.name=%s' % COMMIT_USERNAME,
          '-c', 'user.email=nobody@chromium.org',
          'commit', '-m', 'Synthetic commit for submodules')

  # We've effectively deleted the commit that was at HEAD before. This means
  # that we've diverged from the remote repo, and hence must do a force push.
  api.git('push', '--all', '--force',
          'https://%s/_direct/%s' % (target_host, target_project))


fake_src_deps = """
{
  "src/v8": {
    "url": "https://chromium.googlesource.com/v8/v8.git",
    "rev": "4ad2459561d76217c9b7aff412c5c086b491078a"
  },
  "src/buildtools": {
    "url": "https://chromium.googlesource.com/chromium/buildtools.git",
    "rev": "13a00f110ef910a25763346d6538b60f12845656"
  },
  "src-internal": {
    "url": "https://chromi-internal.googlesource.com/chrome/src-internal.git",
    "rev": "34b7d6a218430e7ff716b81854743a30cfbd3967"
  }
}
"""

def GenTests(api):
  yield (
      api.test('first_time_running') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror',
          buildername='the best builder') +
      api.step_data('Check for existing source checkout dir',
                    # Checkout doesn't exist.
                    api.raw_io.stream_output('', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    # No commits in the target repo.
                    api.json.output({'log': []})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )

  yield (
      api.test('existing_checkout_no_new_commits') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror',
          buildername='the best builder') +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'b' * 40,
                            'author': {'name': COMMIT_USERNAME},
                        },
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data(
          'Check for new commits.Get latest commit hash in source repo',
          api.raw_io.stream_output('a' * 40))
  )

  yield (
      api.test('existing_checkout_new_commits') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror',
          buildername='the best builder') +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'b' * 40,
                            'author': {'name': COMMIT_USERNAME},
                        },
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data(
          'Check for new commits.Get latest commit hash in source repo',
          api.raw_io.stream_output('c' * 40)) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )

  yield (
      api.test('existing_checkout_latest_commit_not_by_bot') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror',
          buildername='the best builder') +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )
