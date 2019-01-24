# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock
import webapp2

from handlers.flake.detection import show_flake
from libs import time_util
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import TestLocation
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from waterfall.test.wf_testcase import WaterfallTestCase


class ShowFlakeTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/flake/detection/ui/show-flake', show_flake.ShowFlake),
  ],
                                       debug=True)

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
        test_label_name=test_label_name,
    )
    flake.component = 'Mock>Component'
    flake.test_location = TestLocation()
    flake.test_location.file_path = '../../some/test/path/a.cc'
    flake.test_location.line_number = 42

    flake.flake_issue_key = flake_issue.key
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
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
            'flake_culprit_key':
                None,
            'issue_id':
                900,
            'issue_link': ('https://monorail-prod.appspot.com/p/chromium/issues'
                           '/detail?id=900'),
            'last_updated_time_by_flake_detection':
                '2018-01-01 00:00:00',
            'monorail_project':
                'chromium',
            'merge_destination_key':
                None,
            'last_updated_time_in_monorail':
                None,
            'last_updated_time_with_analysis_results':
                None,
            'labels': [],
            'status':
                None,
        },
        'flake_issue_key':
            flake_issue.key,
        'luci_project':
            'chromium',
        'last_occurred_time':
            None,
        'last_test_location_based_tag_update_time':
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
        'flake_counts_last_week': [
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
            {
                'flake_type': 'cq hidden flake',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'ci failed step',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
        ],
        'flake_score_last_week':
            0,
        'component':
            'Mock>Component',
        'tags': [],
        'test_location': {
            'file_path': '../../some/test/path/a.cc',
            'line_number': 42,
        },
        'culprits': [],
        'sample_analysis':
            None,
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
                'tags': [],
                'build_id': '123',
                'flake_type': 'cq false rejection',
                'gerrit_cl_id': 98765,
                'step_ui_name': 'step',
                'test_name': 'test',
                'time_detected': '2018-01-01 00:00:00 UTC',
                'time_happened': '2018-01-01 00:00:00 UTC'
            }]
        }]
    }

    self.assertEqual(
        json.dumps({
            'flake_json':
                flake_dict,
            'key':
                flake.key.urlsafe(),
            'show_all_occurrences':
                '',
            'weights': [('cq false rejection', 100),
                        ('cq retry with patch', 10), ('cq hidden flake', 1),
                        ('ci failed step', 10)]
        },
                   default=str,
                   sort_keys=True,
                   indent=2),
        json.dumps(json.loads(response.body), sort_keys=True, indent=2))
