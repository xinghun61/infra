# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handler to update repo_to_dep_path in config."""

from google.appengine.api import app_identity
from google.appengine.api import users

from common.model.crash_config import CrashConfig
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.handlers.base_handler import BaseHandler, Permission
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher


def GetRepoToDepPath(dep_fetcher):
  """Gets mapping from repo_url to dep_path from master branch in chromium."""
  deps = dep_fetcher.GetDependency('master', 'all')
  if not deps:
    return None

  repo_to_dep_path = {}
  for dep in deps.itervalues():
    repo_to_dep_path[dep.repo_url] = dep.path

  return repo_to_dep_path


class UpdateRepoToDepPath(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    """Update the repo_to_dep_path in config from the lastest DEPS."""
    # Update repo_to_dep_path to the latest information.
    dep_fetcher = ChromeDependencyFetcher(
      CachedGitilesRepository.Factory(HttpClientAppengine()))

    repo_to_dep_path = GetRepoToDepPath(dep_fetcher)
    if not repo_to_dep_path:  # pragma: no cover.
      return self.CreateError('Fail to update repo_to_dep_path config.', 400)

    crash_config = CrashConfig.Get()
    crash_config.Update(users.User(app_identity.get_service_account_name()),
                        True, repo_to_dep_path=repo_to_dep_path)
