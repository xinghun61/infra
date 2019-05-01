# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates the Git Cache zip files."""

from recipe_engine import recipe_api

DEPS = [
  'depot_tools/depot_tools',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/runtime',
  'recipe_engine/step',
  'recipe_engine/url',
]


PROPERTIES = {
  'bucket': recipe_api.Property(
      default=None, help='override GS bucket to upload cached git repos to'),
  'repo_urls': recipe_api.Property(
      default=None,
      help='List of repo urls to limit work to just these repos. Each must:\n'
           ' * not have /a/ as path prefix\n'
           ' * no trailing slash\n'
           ' * no .git suffix\n'
           'For example, "https://chromium.googlesource.com/infra/infra".')
}


BUILDER_MAPPING = {
  'git-cache-chromium': 'https://chromium.googlesource.com/',
}

TEST_REPOS = """All-Projects
All-Users
apps
chromium/src
foo/bar"""


def list_host_repos(api, host_url):
  with api.depot_tools.on_path():
    output = api.url.get_text('%s?format=TEXT' % host_url,
                              default_test_data=TEST_REPOS).output
    return ['%s%s' % (host_url, repo)
            for repo in output.splitlines()
            if repo.lower() not in ['all-projects', 'all-users']]


def RunSteps(api, bucket, repo_urls):
  if not repo_urls:
    repo_urls = list_host_repos(
        api, BUILDER_MAPPING[api.buildbucket.builder_name])

  work_dir = api.path['cache'].join('builder', 'w')
  api.file.ensure_directory('ensure work_dir', work_dir)

  env = {
    # Turn off the low speed limit, since checkout will be long.
    'GIT_HTTP_LOW_SPEED_LIMIT': '0',
    'GIT_HTTP_LOW_SPEED_TIME': '0',
    # Ensure git-number tool can be used.
    'CHROME_HEADLESS': '1',
  }
  if api.runtime.is_experimental:
    assert bucket, 'bucket property is required in experimental mode'
    env['OVERRIDE_BOOTSTRAP_BUCKET'] = bucket

  with api.context(env=env):
    # Run the updater script.
    with api.depot_tools.on_path():
      for url in repo_urls:
        api.step(
            name='Updating %s' % url,
            cmd=[
              'git_cache.py', 'update-bootstrap', url,
              '--cache-dir', work_dir,
              '--prune',
              '--reset-fetch-config',
              '--verbose',
              '--ref', 'refs/branch-heads/*',
              # By default, "refs/heads/*" and refs/tags/* are checked out by
              # git_cache. However, for heavy branching repos,
              # 'refs/branch-heads/*' is also very useful (crbug/942169).
              # This is a noop for repos without refs/branch-heads.
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
      api.properties(bucket='experimental-gs-bucket',
                     repo_urls=['https://chromium.googlesource.com/v8/v8']) +
      api.buildbucket.try_build(builder='git-cache-chromium')
  )
