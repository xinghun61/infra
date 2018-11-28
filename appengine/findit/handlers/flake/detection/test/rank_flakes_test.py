# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import webapp2

from handlers.flake.detection import rank_flakes
from libs import time_util
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from waterfall.test.wf_testcase import WaterfallTestCase


class RankFlakesTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/ranked-flakes', rank_flakes.RankFlakes),
  ],
                                       debug=True)

  def setUp(self):
    super(RankFlakesTest, self).setUp()

    self.flake_issue0 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=900)
    self.flake_issue0.last_updated_time = datetime.datetime(2018, 1, 1)
    self.flake_issue0.put()

    self.flake_issue1 = FlakeIssue.Create(
        monorail_project='chromium', issue_id=1000)
    self.flake_issue1.last_updated_time = datetime.datetime(2018, 1, 1)
    self.flake_issue1.merge_destination_key = self.flake_issue0.key
    self.flake_issue1.put()

    self.luci_project = 'chromium'
    self.normalized_step_name = 'normalized_step_name'
    self.flake1 = Flake.Create(
        luci_project=self.luci_project,
        normalized_step_name=self.normalized_step_name,
        normalized_test_name='normalized_test_name',
        test_label_name='normalized_test_name')

    self.flake1.flake_issue_key = self.flake_issue1.key
    self.flake1.false_rejection_count_last_week = 3
    self.flake1.impacted_cl_count_last_week = 2
    self.flake1.flake_score_last_week = 0
    self.flake1.last_occurred_time = datetime.datetime(2018, 10, 1)
    self.flake1.put()

    self.flake2 = Flake.Create(
        luci_project=self.luci_project,
        normalized_step_name=self.normalized_step_name,
        normalized_test_name='suite.test1',
        test_label_name='suite.test1')
    self.flake2.put()

    self.flake3 = Flake.Create(
        luci_project=self.luci_project,
        normalized_step_name=self.normalized_step_name,
        normalized_test_name='suite.test2',
        test_label_name='suite.test2')
    self.flake3.false_rejection_count_last_week = 5
    self.flake3.impacted_cl_count_last_week = 3
    self.flake3.flake_score_last_week = 10800
    self.flake3.last_occurred_time = datetime.datetime(2018, 10, 1)
    self.flake3.flake_issue_key = self.flake_issue0.key
    self.flake3.tags = ['suite::suite', 'test_type::flavored_tests']
    self.flake3.put()

    self.flake4 = Flake.Create(
        luci_project=self.luci_project,
        normalized_step_name=self.normalized_step_name,
        normalized_test_name='suite.test3',
        test_label_name='suite.test3')
    self.flake4.false_rejection_count_last_week = 5
    self.flake4.impacted_cl_count_last_week = 3
    self.flake4.flake_score_last_week = 1080
    self.flake4.last_occurred_time = datetime.datetime(2018, 10, 1)
    self.flake4.tags = ['test_type::tests']
    self.flake4.put()

    self.flake1_dict = self.flake1.to_dict()
    self.flake1_dict['flake_issue'] = self.flake_issue0.to_dict()
    self.flake1_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        self.flake_issue0.monorail_project, self.flake_issue0.issue_id)

    self.flake3_dict = self.flake3.to_dict()
    self.flake3_dict['flake_issue'] = self.flake_issue0.to_dict()
    self.flake3_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        self.flake_issue0.monorail_project, self.flake_issue0.issue_id)

    self.flake4_dict = self.flake4.to_dict()

    for data, flake in ((self.flake1_dict, self.flake1),
                        (self.flake3_dict, self.flake3), (self.flake4_dict,
                                                          self.flake4)):
      data['flake_urlsafe_key'] = flake.key.urlsafe()
      data['time_delta'] = '1 day, 01:00:00'
      data['flake_counts_last_week'] = [
          {
              'flake_type': 'cq false rejection',
              'impacted_cl_count': 0,
              'occurrence_count': 0
          },
          {
              'flake_type': 'cq retry with patch',
              'impacted_cl_count': 0,
              'occurrence_count': 0
          },
      ]

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testRankFlakes(self, _):
    response = self.test_app.get(
        '/ranked-flakes', params={
            'format': 'json',
        }, status=200)

    self.assertEqual(
        json.dumps({
            'flakes_data': [self.flake3_dict, self.flake4_dict],
            'prev_cursor':
                '',
            'cursor':
                '',
            'n':
                '',
            'luci_project':
                '',
            'flake_filter':
                '',
            'bug_id':
                '',
            'monorail_project': '',
            'error_message':
                None,
            'flake_weights': [('cq false rejection', 100),
                              ('cq retry with patch', 10)]
        },
                   default=str), response.body)

  @mock.patch.object(Flake, 'NormalizeTestName', return_value='suite.test2')
  def testSearchRedirect(self, _):
    response = self.test_app.get(
        '/ranked-flakes?flake_filter=test_name',
        params={
            'format': 'json',
        },
        status=302)

    expected_url_suffix = (
        '/flake/occurrences?key=%s' % self.flake3.key.urlsafe())

    self.assertTrue(
        response.headers.get('Location', '').endswith(expected_url_suffix))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testGetFlakesBySimpleSearch(self, _):
    response = self.test_app.get(
        '/ranked-flakes?flake_filter=suite::suite',
        params={
            'format': 'json',
        },
        status=200)

    self.assertEqual(
        json.dumps({
            'flakes_data': [self.flake3_dict],
            'prev_cursor':
                '',
            'cursor':
                '',
            'n':
                '',
            'luci_project':
                '',
            'flake_filter':
                'suite::suite',
            'bug_id':
                '',
            'monorail_project': '',
            'error_message':
                None,
            'flake_weights': [('cq false rejection', 100),
                              ('cq retry with patch', 10)]
        },
                   default=str), response.body)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testGetFlakesByAdvancedSearch(self, _):
    response = self.test_app.get(
        '/ranked-flakes?flake_filter='
        'test_type::flavored_tests@-test_type::tests',
        params={
            'format': 'json',
        },
        status=200)

    self.assertEqual(
        json.dumps({
            'flakes_data': [self.flake3_dict],
            'prev_cursor':
                '',
            'cursor':
                '',
            'n':
                '',
            'luci_project':
                '',
            'flake_filter':
                'test_type::flavored_tests@-test_type::tests',
            'bug_id':
                '',
            'monorail_project': '',
            'error_message':
                None,
            'flake_weights': [('cq false rejection', 100),
                              ('cq retry with patch', 10)]
        },
                   default=str), response.body)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testGetFlakesByMergedBugKey(self, _):
    bug_id = self.flake_issue0.issue_id
    response = self.test_app.get(
        '/ranked-flakes?bug_id=%s' % bug_id,
        params={
            'format': 'json',
        },
        status=200)

    self.assertEqual(
        json.dumps({
            'flakes_data': [self.flake3_dict, self.flake1_dict],
            'prev_cursor':
                '',
            'cursor':
                '',
            'n':
                '',
            'luci_project':
                '',
            'flake_filter':
                '',
            'bug_id':
                bug_id,
            'monorail_project': '',
            'error_message':
                None,
            'flake_weights': [('cq false rejection', 100),
                              ('cq retry with patch', 10)]
        },
                   default=str), response.body)

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testGetFlakesByIndependentBugKey(self, _):
    bug_id = self.flake_issue1.issue_id
    response = self.test_app.get(
        '/ranked-flakes?bug_id=%s' % bug_id,
        params={
            'format': 'json',
        },
        status=200)

    self.assertEqual(
        json.dumps({
            'flakes_data': [self.flake1_dict],
            'prev_cursor':
                '',
            'cursor':
                '',
            'n':
                '',
            'luci_project':
                '',
            'flake_filter':
                '',
            'bug_id':
                bug_id,
            'monorail_project': '',
            'error_message':
                None,
            'flake_weights': [('cq false rejection', 100),
                              ('cq retry with patch', 10)]
        },
                   default=str), response.body)
