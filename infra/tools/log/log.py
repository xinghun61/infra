# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Log."""

# Note: Don't mind the littering of pragma no cover statements in the file,
# most of this file is actually covered, they're here because of phantom
# branch misses.

import datetime
import httplib2
import logging
import oauth2client.client
import os
import sys
import time

from googleapiclient import discovery
from oauth2client.client import OAuth2WebServerFlow


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)

# All Chrome related logs go here.
PROJECT_ID = 'chrome-infra-logs'
# We put everything under this service name.
SERVICE_NAME = 'compute.googleapis.com'
# All of the relevent tables are in this dataset.
DATASET_ID = 'logs'

CACHE_FILE = os.path.join(
    os.path.expanduser('~'), '.config', 'chrome_infra', 'auth',
    'cloud_logging.json')

CAT_QUERY = """
SELECT timestamp, textPayload, labels.cloudtail_resource_id
FROM TABLE_DATE_RANGE(
    %s.%%s_,
    DATE_ADD(CURRENT_TIMESTAMP(), %%d, 'DAY'),
    DATE_ADD(CURRENT_TIMESTAMP(), %%d, 'DAY')),
""" % DATASET_ID

LIST_QUERY = """
SELECT labels.cloudtail_resource_id
FROM TABLE_DATE_RANGE(
    %s.%%s_,
    DATE_ADD(CURRENT_TIMESTAMP(), %%d, 'DAY'),
    DATE_ADD(CURRENT_TIMESTAMP(), %%d, 'DAY')),
GROUP BY labels.cloudtail_resource_id
""" % DATASET_ID


class LogQuery(object):
  def __init__(self, project, service, limit, days_from, days_until):
    self._api = None
    self.project = project
    self.service = service
    self.limit = limit
    self.days_from = days_from
    self.days_until = days_until

    self._bq = None
    self._http = None
    self._creds = None

  @staticmethod
  def _auth():  # pragma: no cover
    flow = OAuth2WebServerFlow(
        # This belongs to the chrome-infra-logs project.
        client_id='410962439126-g1t7r572gam70qcehd49a1n5gq1lj814'
                  '.apps.googleusercontent.com',
        # This is not actually a secret, it's more like an API key.
        client_secret='VqOcmdXVRIgMekbFfu2eDzEL',
        scope=['https://www.googleapis.com/auth/bigquery'],
        # For simplicity, the local webserver flow is disabled.  It's a flaky
        # flow anyways because if you have multiple Chrome profiles, which
        # profile gets chosen is anyone's guess.
        redirect_uri=oauth2client.client.OOB_CALLBACK_URN)
    authorize_url = flow.step1_get_authorize_url()
    print 'Go to URL: %s' % authorize_url
    code = raw_input('Enter verification code: ').strip()
    creds = flow.step2_exchange(code)
    if not os.path.exists(os.path.dirname(CACHE_FILE)):
      os.makedirs(os.path.dirname(CACHE_FILE))
    with open(CACHE_FILE, 'wb') as f:
      f.write(creds.to_json())
    return creds

  def _get_auth(self):  # pragma: no cover
    if not os.path.exists(CACHE_FILE):
      return self._auth()
    with open(CACHE_FILE, 'r') as f:
      return oauth2client.client.OAuth2Credentials.from_json(f.read())

  def _actually_init(self):  # pragma: no cover
    self._creds = self._get_auth()
    self._http = self._creds.authorize(httplib2.Http())
    self._bq = discovery.build('bigquery', 'v2', http=self._http)

  def cat(self, targets, limit=None):
    assert len(targets) in (1, 2)
    log_name = targets[0]
    resource_id = None
    if len(targets) == 2:
      resource_id = targets[1]
    else:
      print >>sys.stderr, (
          'WARNING: Querying for all resources under a service, '
          'this may take a long time...')
    if not limit:  # pragma: no branch
      limit = self.limit
    tzoffset = datetime.timedelta(
        seconds=time.altzone if time.daylight else time.timezone)
    offset = time.altzone / 60 / 60
    print >>sys.stderr, (
        'NOTE: All times are in local system time (%g hour(s)).' % -offset)
    q = CAT_QUERY % (log_name, self.days_from, self.days_until)
    if resource_id:
      q += '\n WHERE labels.cloudtail_resource_id = "%s"' % resource_id
    # ORDER BY always comes after WHERE
    q += ' ORDER BY timestamp DESC'
    # LIMIT has to be the last thing in the query.
    q += ' LIMIT %d' % limit
    LOGGER.debug(q)
    j = self._bq.jobs().query(
        projectId=PROJECT_ID,
        body={
            'query': q,
            'maxResults': 1000,
            'allowLargeResults': True}).execute()
    # TODO(hinoka): Retry with a lower limit if this 403's.
    # TODO(hinoka): Maybe timeout?
    if not j['jobComplete']:
      # If the job takes more than 10s to complete, then we have to continually
      # poll for the job, since BigQuery doesn't give us partial results.
      job_id = j['jobReference']['jobId']
      while True:
        print >>sys.stderr, 'Still working... (Job ID: %s)' % job_id
        # inner job
        ij = self._bq.jobs().getQueryResults(
            projectId=PROJECT_ID, jobId=job_id,
            timeoutMs=1000, maxResults=1000).execute()
        if not ij['jobComplete']:  # pragma: no cover
          continue
        j = ij
        break

    lines = []
    while True:
      for row in j.get('rows', []):
        ts_f = row['f'][0]['v']  # Bigquery returns timestamps as float strings.
        line = row['f'][1]['v']  # textPayload
        resource = row['f'][2]['v']  # metadata.labels.value
        utc_ts = datetime.datetime.utcfromtimestamp(float(ts_f))
        local_ts = utc_ts - tzoffset
        local_ts_str = local_ts.strftime('%Y-%m-%d %I:%M:%S%p')
        if resource_id:
          lines.append('%s: %s' % (local_ts_str, line))
        else:
          lines.append('%s (%s): %s' % (local_ts_str, resource, line))
      if not j.get('pageToken'):  # pragma: no branch
        break
      # Should finish immediately.
      j = self._bq.jobs().getQueryResults(  # pragma: no cover
          projectId=PROJECT_ID, jobId=j['jobReference']['jobId'],
          maxResults=1000, pageToken=j['pageToken']).execute()

    for line in reversed(lines):
      print line

  def _list_logs_names(self):
    """List all of the log names in a project."""
    tables = []
    nextPage = None
    while True:
      page = self._bq.tables().list(
          projectId=PROJECT_ID, datasetId=DATASET_ID,
          pageToken=nextPage, maxResults=1000).execute()
      tables.extend(page['tables'])
      if not page.get('nextPageToken'):  # pragma: no branch
        break
      nextPage = page['nextPageToken']  # pragma: no cover

    names = set()
    for table in tables:
      # 9 represents the _YYYYMMDD postfix of the tablename.
      names.add(table['tableReference']['tableId'][:-9])

    for name in sorted(names):
      print name

  def _list_resources(self, log_name):
    """List all resources associated with a log name."""
    q = LIST_QUERY % (log_name, self.days_from, self.days_until)
    LOGGER.debug(q)
    j = self._bq.jobs().query(
        projectId=PROJECT_ID, body={'query': q}).execute()
    for row in sorted(j['rows'], key=lambda x: x['f'][0]['v']):
      print row['f'][0]['v']

  def list_logs(self, log_name):
    if log_name:
      return self._list_resources(log_name)
    return self._list_logs_names()
