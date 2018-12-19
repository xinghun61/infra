# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from services import flake_issue_util


class UpdateOpenFlakeIssuesCron(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    # Runs a cron job to update open FlakeIssue entities.
    taskqueue.add(
        method='GET',
        queue_name=constants.AUTO_ACTION_QUEUE,
        target=constants.AUTO_ACTION_BACKEND,
        url='/auto-action/task/update-open-flake-issues')
    return {'return_code': 200}


class UpdateOpenFlakeIssuesTask(BaseHandler):
  """Updates open FlakeIssues for parity with issues in Monorail."""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    flake_issue_util.SyncOpenFlakeIssuesWithMonorail()
    return {'return_code': 200}
