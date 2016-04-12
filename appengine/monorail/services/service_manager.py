# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Service manager to initialize all services."""

from features import autolink
from services import cachemanager_svc
from services import config_svc
from services import features_svc
from services import issue_svc
from services import project_svc
from services import spam_svc
from services import star_svc
from services import user_svc
from services import usergroup_svc


svcs = None


class Services(object):
  """A simple container for widely-used service objects."""

  def __init__(
      self, project=None, user=None, issue=None, config=None,
      inboundemail=None, usergroup=None, cache_manager=None, autolink_obj=None,
      user_star=None, project_star=None, issue_star=None, features=None,
      spam=None):
    # Persistence services
    self.project = project
    self.user = user
    self.usergroup = usergroup
    self.issue = issue
    self.config = config
    self.user_star = user_star
    self.project_star = project_star
    self.issue_star = issue_star
    self.features = features
    self.spam = spam

    # Misc. services
    self.cache_manager = cache_manager
    self.inboundemail = inboundemail
    self.autolink = autolink_obj


def set_up_services():
  """Set up all services."""

  global svcs
  if svcs is None:
    svcs = Services()
    svcs.autolink = autolink.Autolink()
    svcs.cache_manager = cachemanager_svc.CacheManager()
    svcs.user = user_svc.UserService(svcs.cache_manager)
    svcs.user_star = star_svc.UserStarService(svcs.cache_manager)
    svcs.project_star = star_svc.ProjectStarService(svcs.cache_manager)
    svcs.issue_star = star_svc.IssueStarService(svcs.cache_manager)
    svcs.project = project_svc.ProjectService(svcs.cache_manager)
    svcs.usergroup = usergroup_svc.UserGroupService(svcs.cache_manager)
    svcs.config = config_svc.ConfigService(svcs.cache_manager)
    svcs.issue = issue_svc.IssueService(
        svcs.project, svcs.config, svcs.cache_manager)
    svcs.features = features_svc.FeaturesService(svcs.cache_manager)
    svcs.spam = spam_svc.SpamService()
  return svcs
