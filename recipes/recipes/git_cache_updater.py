# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates the Git Cache zip files."""

from recipe_engine import recipe_api

DEPS = [
  'depot_tools/depot_tools',
  'depot_tools/gclient',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/url',
]


PROPERTIES = {
  'bucket': recipe_api.Property(
      default=None, help='override GS bucket to upload cached git repos to'),
}


BUILDER_MAPPING = {
  'git-cache-chromium': 'https://chromium.googlesource.com/',
}

TEST_REPOS = """All-Projects
All-Users
apps
chromium/src
foo/bar"""


def RunSteps(api, bucket):
  project = BUILDER_MAPPING[api.buildbucket.builder_name]
  project_list_url = '%s?format=TEXT' % project

  api.gclient.set_config('infra')
  api.gclient.c.solutions[0].revision = 'origin/master'
  api.gclient.checkout()
  api.gclient.runhooks()

  env = {
    'GIT_HTTP_LOW_SPEED_LIMIT': '0',
    'GIT_HTTP_LOW_SPEED_TIME': '0',
  }
  if api.runtime.is_experimental:
    assert bucket, 'bucket property is required in experimental mode'
    env['OVERRIDE_BOOTSTRAP_BUCKET'] = bucket

  # Turn off the low speed limit, since checkout will be long.
  with api.context(env=env):
    # Run the updater script.
    with api.depot_tools.on_path():
      repos = api.url.get_text(project_list_url, default_test_data=TEST_REPOS)
      for repo in repos.output.splitlines():
        if repo.lower() in ['all-projects', 'all-users']:
          continue
        url = '%s%s' % (project, repo)
        api.python(
            'Updating %s' % url,
            api.path['start_dir'].join('infra', 'run.py'),
            [
              'infra.services.git_cache_updater',
              '--repo', url,
            '--work-dir', api.path['start_dir'].join('cache_dir')
          ],
          # It's fine for this to fail, just move on to the next one.
          ok_ret='any')


def GenTests(api):
  yield (
      api.test('git-cache-chromium') +
      api.buildbucket.try_build(builder='git-cache-chromium')
  )
  yield (
      api.test('git-cache-chromium-led-triggered') +
      api.runtime(is_luci=True, is_experimental=True) +
      api.properties(bucket='experimental-gs-bucket') +
      api.buildbucket.try_build(builder='git-cache-chromium')
  )
