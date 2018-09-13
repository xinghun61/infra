# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock
import webapp2

from handlers.flake.detection import show_flake
from libs import time_util
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)
from waterfall.test.wf_testcase import WaterfallTestCase


class ShowFlakeTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/ui/show-flake', show_flake.ShowFlake),
      ], debug=True)

  def testParameterHasNoKey(self):
    response = self.test_app.get(
        '/flake/detection/ui/show-flake',
        params={
            'format': 'json',
        },
        status=404)
    self.assertEqual('Key is required to identify a flaky test.',
                     response.json_body.get('error_message'))

  def testFlakeNotFound(self):
    response = self.test_app.get(
        '/flake/detection/ui/show-flake',
        params={
            'format': 'json',
            'key': '123',
        },
        status=404)
    self.assertEqual('Didn\'t find Flake for key 123.',
                     response.json_body.get('error_message'))

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2018, 1, 3))
  def testShowFlake(self, _):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = datetime(2018, 1, 1)
    flake_issue.put()

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)

    flake.flake_issue_key = flake_issue.key
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    response = self.test_app.get(
        '/flake/detection/ui/show-flake',
        params={
            'key': flake.key.urlsafe(),
            'format': 'json',
        },
        status=200)

    flake_dict = {
        'flake_issue': {
            'issue_id':
                900,
            'issue_link': ('https://monorail-prod.appspot.com/p/chromium/issues'
                           '/detail?id=900'),
            'last_updated_time_by_flake_detection':
                '2018-01-01 00:00:00',
            'monorail_project':
                'chromium'
        },
        'flake_issue_key':
            flake_issue.key,
        'luci_project':
            'chromium',
        'last_occurred_time':
            None,
        'normalized_step_name':
            'normalized_step_name',
        'normalized_test_name':
            'normalized_test_name',
        'test_label_name':
            'test_label',
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'occurrences': [{
            'group_by_field':
                'luci builder',
            'occurrences': [{
                'build_configuration': {
                    'legacy_build_number': 999,
                    'legacy_master_name': 'buildbot master',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder',
                    'luci_project': 'chromium'
                },
                'build_id': '123',
                'gerrit_cl_id': 98765,
                'step_ui_name': 'step',
                'test_name': 'test',
                'time_detected': '2018-01-01 00:00:00 UTC',
                'time_happened': '2018-01-01 00:00:00 UTC'
            }]
        }]
    }

    self.assertEqual(
        json.dumps(
            {
                'flake_json': flake_dict
            }, default=str, sort_keys=True, indent=2),
        json.dumps(json.loads(response.body), sort_keys=True, indent=2))
