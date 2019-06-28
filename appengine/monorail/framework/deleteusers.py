# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""Cron and task handlers for syncing with wipeoute-lite and deleting users."""

from businesslogic import work_env
from framework import framework_constants
from framework import jsonfeed

class DeleteUsersTask(jsonfeed.InternalTask):

  def HandleRequest(self, mr):
    """Delete users with the emails given in the 'emails' param."""
    # TODO(jojwang): monorail:5740, remove default_value when
    # deleted user_id transition is done.
    emails = mr.GetListParam(
        'emails', default_value=['deleted_user_email@test.test'])
    assert len(emails) <= framework_constants.MAX_DELETE_USERS_SIZE, (
        'We cannot delete more than %d users at once, current users: %d' %
        (framework_constants.MAX_DELETE_USERS_SIZE, len(emails)))
    with work_env.WorkEnv(mr, self.services) as we:
      we.ExpungeUsers(emails, check_perms=False)
