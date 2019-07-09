# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""Cron and task handlers for syncing with wipeoute-lite and deleting users."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from businesslogic import work_env
from framework import framework_constants
from framework import jsonfeed

class DeleteUsersTask(jsonfeed.InternalTask):

  def HandleRequest(self, mr):
    """Delete users with the emails given in the 'emails' param."""
    emails = mr.GetListParam('emails', default_value=[])
    assert len(emails) <= framework_constants.MAX_DELETE_USERS_SIZE, (
        'We cannot delete more than %d users at once, current users: %d' %
        (framework_constants.MAX_DELETE_USERS_SIZE, len(emails)))
    if len(emails) == 0:
      logging.info("No user emails found in deletion request")
      return
    with work_env.WorkEnv(mr, self.services) as we:
      we.ExpungeUsers(emails, check_perms=False)
