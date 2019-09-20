# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates the Git Cache zip files."""

import re

from recipe_engine import recipe_api
from PB.recipe_engine import result as result_pb
from PB.go.chromium.org.luci.buildbucket.proto import common as bb_common_pb

from PB.recipes.infra import git_cache_updater as git_cache_updater_pb


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

PROPERTIES = git_cache_updater_pb.Inputs


# TODO(tandrii): delete this.
BUILDER_MAPPING = {
  'git-cache-chromium': 'https://chromium.googlesource.com/',
}


def _list_host_repos(api, host_url):
  host_url = host_url.rstrip('/')
  with api.depot_tools.on_path():
    output = api.url.get_text('%s/?format=TEXT' % host_url,
                              default_test_data=TEST_REPOS).output
    return output.strip().splitlines()


def _repos_to_urls(host_url, repos):
  host_url = host_url.rstrip('/')
  return ['%s/%s' % (host_url, repo) for repo in repos]


class _InvalidRegexp(Exception):
  pass


def _get_repo_urls(api, inputs):
  if inputs.git_host.host:
    assert not inputs.repo_urls, 'only 1 of (git_host, repo_urls) allowed'
    repos = _list_host_repos(api, 'https://' + inputs.git_host.host)
    if inputs.git_host.exclude_repos:
      exclude_regexps = []
      for i, r in enumerate(inputs.git_host.exclude_repos):
        try:
          exclude_regexps.append(re.compile('^' + r + '$', re.IGNORECASE))
        except Exception as e:
          raise _InvalidRegexp(
              'invalid regular expression[%d] %r: %s' % (i, r, e))
      repos = [repo for repo in repos
               if all(not r.match(repo) for r in exclude_regexps)]
    return _repos_to_urls('https://' + inputs.git_host.host, repos)

  if inputs.repo_urls:
    return list(inputs.repo_urls)

  # Legacy. TODO(tandrii): remove this.
  host_url = BUILDER_MAPPING[api.buildbucket.builder_name]
  repos = [repo for repo in _list_host_repos(api, host_url)
           if repo.lower() not in ('all-projects', 'all-users')]
  return _repos_to_urls(host_url, repos)


def RunSteps(api, inputs):
  try:
    repo_urls = _get_repo_urls(api, inputs)
  except _InvalidRegexp as e:
    return result_pb.RawResult(
        status=bb_common_pb.FAILURE,
        summary_markdown=e.message)

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
    assert inputs.override_bucket, 'override_bucket required for experiments'
  if inputs.override_bucket:
    env['OVERRIDE_BOOTSTRAP_BUCKET'] = inputs.override_bucket

  with api.context(env=env):
    # Run the updater script.
    with api.depot_tools.on_path():
      for url in sorted(repo_urls):
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
  return result_pb.RawResult(
      status=bb_common_pb.SUCCESS,
      summary_markdown='Updated cache for %d repos' % len(repo_urls),
  )


TEST_REPOS = """
All-Projects
All-Users
apps
chromium/src
foo/bar
"""


def GenTests(api):
  yield (
      # TODO(tandrii): remove this legacy buildername-based config.
      api.test('git-cache-chromium')
      + api.buildbucket.try_build(builder='git-cache-chromium')
  )
  yield (
      api.test('one-repo-experiment')
      + api.runtime(is_experimental=True, is_luci=True)
      + api.properties(git_cache_updater_pb.Inputs(
          override_bucket='experimental-gs-bucket',
          repo_urls=['https://chromium.googlesource.com/v8/v8'],
      ))
  )
  yield (
      api.test('host-with-exclusions')
      + api.properties(git_cache_updater_pb.Inputs(
          git_host=git_cache_updater_pb.Inputs.GitHost(
              host='chromium.googlesource.com',
              exclude_repos=[
                'foo/.+',
                'all-projects',
                'all-users',
              ],
          ),
      ))
  )
  yield (
      api.test('host-with-incorrect-regexp-exclude')
      + api.properties(git_cache_updater_pb.Inputs(
          git_host=git_cache_updater_pb.Inputs.GitHost(
              host='chromium.googlesource.com',
              exclude_repos=[
                '?.\\',
              ],
          ),
      ))
  )
