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
MAX_DELETE_USERS_SIZE = 1000


def authorize():
  credentials = GoogleCredentials.get_application_default()
  credentials = credentials.create_scoped(framework_constants.OAUTH_SCOPE)
  return credentials.authorize(httplib2.Http(timeout=60))


class WipeoutSyncCron(jsonfeed.InternalTask):
  """Enqueue tasks for sending user lists to wipeout-lite and deleting deleted
     users fetched from wipeout-lite."""

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

    taskqueue.add(
        url=urls.DELETE_WIPEOUT_USERS_TASK + '.do',
        queue_name=framework_constants.QUEUE_FETCH_WIPEOUT_DELETED_USERS)


class SendWipeoutUserListsTask(jsonfeed.InternalTask):
  """Sends a batch of monorail users to wipeout-lite."""

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


class DeleteWipeoutUsersTask(jsonfeed.InternalTask):
  """Fetches deleted users from wipeout-lite and enqueues tasks to delete
     those users from Monorail's DB."""

  def HandleRequest(self, mr):
    limit = mr.GetIntParam('limit', MAX_DELETE_USERS_SIZE)
    limit = min(limit, MAX_DELETE_USERS_SIZE)
    service = authorize()
    deleted_user_data = self.fetchDeletedUsers(service)
    deleted_emails = [user_object['id'] for user_object in deleted_user_data]
    total_batches = int(len(deleted_emails) / limit)
    if len(deleted_emails) % limit:
      total_batches += 1

    for i in range(total_batches):
      start = i * limit
      end = start + limit
      params = dict(emails=','.join(deleted_emails[start:end]))
      taskqueue.add(
          url=urls.DELETE_USERS_TASK + '.do', params=params,
          queue_name=framework_constants.QUEUE_DELETE_USERS)

  def fetchDeletedUsers(self, service):
    app_id = app_identity.get_application_id()
    endpoint = WIPEOUT_ENDPOINT % app_id
    resp, data = service.request(
        '%s/deletedaccounts' % endpoint,
        method='GET',
        headers={'Content-Type': 'application/json; charset=UTF-8'})
    logging.info(
        'Received response, %s with contents, %s', resp, data)
    return json.loads(data)


class DeleteUsersTask(jsonfeed.InternalTask):
  """Deletes users from Monorail's DB."""

  def HandleRequest(self, mr):
    """Delete users with the emails given in the 'emails' param."""
    emails = mr.GetListParam('emails', default_value=[])
    assert len(emails) <= MAX_DELETE_USERS_SIZE, (
        'We cannot delete more than %d users at once, current users: %d' %
        (MAX_DELETE_USERS_SIZE, len(emails)))
    if len(emails) == 0:
      logging.info("No user emails found in deletion request")
      return
    with work_env.WorkEnv(mr, self.services) as we:
      we.ExpungeUsers(emails, check_perms=False)
