# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""Cron and task handlers for syncing with wipeoute-lite and deleting users."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging
import httplib2

from google.appengine.api import app_identity
from google.appengine.api import taskqueue

from businesslogic import work_env
from framework import framework_constants
from framework import jsonfeed
from framework import urls
from oauth2client.client import GoogleCredentials

WIPEOUT_ENDPOINT = 'https://emporia-pa.googleapis.com/v1/apps/%s'
MAX_BATCH_SIZE = 10000


def authorize():
  credentials = GoogleCredentials.get_application_default()
  credentials = credentials.create_scoped(framework_constants.OAUTH_SCOPE)
  return credentials.authorize(httplib2.Http(timeout=60))


class WipeoutSyncCron(jsonfeed.InternalTask):

  def HandleRequest(self, mr):
    batch_param = mr.GetIntParam('batchsize', default_value=MAX_BATCH_SIZE)
    # Use batch_param as batch_size unless it is None or 0.
    batch_size = min(batch_param, MAX_BATCH_SIZE)
    total_users = self.services.user.TotalUsersCount(mr.cnxn)
    total_batches = int(total_users / batch_size)
    # Add an extra batch to process remainder user emails.
    if total_users % batch_size:
      total_batches += 1
    if not total_batches:
      logging.info('No users to report.')
      return

    for i in range(total_batches):
      params = dict(limit=batch_size, offset=i * batch_size)
      taskqueue.add(
          url=urls.SEND_WIPEOUT_USER_LISTS_TASK + '.do', params=params,
          queue_name=framework_constants.QUEUE_SEND_WIPEOUT_USER_LISTS)


class SendWipeoutUserListsTask(jsonfeed.InternalTask):

  def HandleRequest(self, mr):
    limit = mr.GetIntParam('limit')
    assert limit != None, 'Missing param limit'
    offset = mr.GetIntParam('offset')
    assert offset != None, 'Missing param offset'
    emails = self.services.user.GetAllUserEmailsBatch(
        mr.cnxn, limit=limit, offset=offset)
    accounts = [{'id': email} for email in emails]
    service = authorize()
    self.sendUserLists(service, accounts)

  def sendUserLists(self, service, accounts):
    app_id = app_identity.get_application_id()
    endpoint = WIPEOUT_ENDPOINT % app_id
    resp, data = service.request(
        '%s/verifiedaccounts' % endpoint,
        method='POST',
        headers={'Content-Type': 'application/json; charset=UTF-8'},
        body=json.dumps(accounts))
    logging.info(
        'Received response, %s with contents, %s', resp, data)


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
