# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../log.py"""

import argparse
import unittest
import mock

from infra.tools.log import log


def bq_row(*args):
  return { 'f': [{'v': v} for v in args] }

class LogQueryTests(unittest.TestCase):
  def setUp(self):
    self.lq = log.LogQuery('Project', 'Service', 2000, -2, 0)
    self.lq._bq = mock.MagicMock()

  def test_cat(self):
    job_result = mock.MagicMock()
    job_result.execute.return_value = {
      'jobComplete': True,
      'rows': [
        bq_row(12345.12, 'line1', ''),
        bq_row(12345.13, 'line2', '')
      ]
    }
    self.lq._bq.jobs().query.return_value = job_result
    self.lq.cat(['some_resource'])
    q = log.CAT_QUERY % ('some_resource', -2, 0)
    q += ' ORDER BY timestamp DESC LIMIT 2000'
    self.lq._bq.jobs().query.assert_called_with(
        body={
            'query': q,
            'allowLargeResults': True,
            'maxResults': 1000
        },
        projectId='chrome-infra-logs')

  def test_cat2(self):
    job_result = mock.MagicMock()
    job_result.execute.return_value = {
      'jobComplete': True,
      'rows': [
        bq_row(12345.12, 'line1', ''),
        bq_row(12345.13, 'line2', '')
      ]
    }
    self.lq._bq.jobs().query.return_value = job_result
    self.lq.cat(['some_resource', 'some_target'])
    q = log.CAT_QUERY % ('some_resource', -2, 0)
    q += '\n WHERE labels.cloudtail_resource_id = "some_target"'
    q += ' ORDER BY timestamp DESC LIMIT 2000'
    self.lq._bq.jobs().query.assert_called_with(
        body={
            'query': q,
            'allowLargeResults': True,
            'maxResults': 1000
        },
        projectId='chrome-infra-logs')

  def test_cat_long_job(self):
    job_result = mock.MagicMock()
    job_result.execute.return_value = {
      'jobComplete': False,
      'jobReference': {
          'jobId': 'SomeID',
      }
    }
    job_result2 = mock.MagicMock()
    job_result2.execute.return_value = {
      'jobComplete': True,
      'rows': [
        bq_row(12345.12, 'line1', ''),
        bq_row(12345.13, 'line2', '')
      ]
    }
    self.lq._bq.jobs().query.return_value = job_result
    self.lq._bq.jobs().getQueryResults.return_value = job_result2
    self.lq.cat(['some_resource'])

    q = log.CAT_QUERY % ('some_resource', -2, 0)
    q += ' ORDER BY timestamp DESC LIMIT 2000'
    self.lq._bq.jobs().query.assert_called_with(
        body={
            'query': q,
            'allowLargeResults': True,
            'maxResults': 1000
        },
        projectId='chrome-infra-logs')
    self.lq._bq.jobs().getQueryResults.assert_called_with(
        projectId='chrome-infra-logs',
        jobId='SomeID', timeoutMs=1000, maxResults=1000)

  def test_list_log_names(self):
    self.lq._bq.tables().list().execute.return_value = {
        'tables': [
            {'tableReference': {
                'tableId': 'build_logs_123456789'
            }}
        ]
    }
    self.lq.list_logs(None)
    self.lq._bq.tables().list.assert_called_with(
        projectId=log.PROJECT_ID, datasetId='logs',
        pageToken=None, maxResults=1000
    )

  def test_list_resources(self):
    q = log.LIST_QUERY % ('Name', -2, 0)
    self.lq._bq.jobs().query().execute.return_value = {
        'rows': [
            bq_row('Thing 1'),
            bq_row('Thing 2')
        ]
    }
    self.lq.list_logs('Name')
    self.lq._bq.jobs().query.assert_called_with(
      projectId=log.PROJECT_ID, body={'query': q}
    )
