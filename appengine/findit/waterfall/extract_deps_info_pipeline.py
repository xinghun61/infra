# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from libs.deps import chrome_dependency_fetcher
from services import deps


class ExtractDEPSInfoPipeline(BasePipeline):
  """A pipeline to extract information of DEPS and dependency rolls."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info, change_logs):
    """
    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().
      change_logs (dict): Output of pipeline PullChangelogPipeline.run().

    Returns:
      A dict with the following form:
      {
        'deps': {
          'path/to/dependency/': {
            'revision': 'git_hash',
            'repo_url': 'https://url/to/dependency/repo.git',
          },
          ...
        },
        'deps_rolls': {
          'git_revision': [
            {
              'path': 'src/path/to/dependency/',
              'repo_url': 'https://url/to/dependency/repo.git',
              'new_revision': 'git_hash1',
              'old_revision': 'git_hash2',
            },
            ...
          ],
          ...
        }
      }
    """

    chromium_revision = failure_info['chromium_revision']
    os_platform = deps.GetOSPlatformName(failure_info['master_name'],
                                         failure_info['builder_name'])

    dep_fetcher = chrome_dependency_fetcher.ChromeDependencyFetcher(
        CachedGitilesRepository.Factory(HttpClientAppengine()))

    return {
        'deps':
            deps.GetDependencies(chromium_revision, os_platform, dep_fetcher),
        'deps_rolls':
            deps.DetectDependencyRolls(change_logs, os_platform, dep_fetcher)
    }
