# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from parameterized import parameterized

from google.appengine.ext import ndb

from handlers.disabled_tests.detection import disabled_test_detection_utils
from model.flake.flake_issue import FlakeIssue
from model.test_inventory import LuciTest

from waterfall.test.wf_testcase import WaterfallTestCase


class DisabledTestDetectionUtilsTest(WaterfallTestCase):

  # pylint: disable=line-too-long
  def testGenerateDisabledTestsData(self):
    disabled_test_key = LuciTest.CreateKey('a', 'b', 'c')
    disabled_tests = [
        LuciTest(
            key=disabled_test_key,
            disabled_test_variants={('os:Mac1234',), ('Unknown',)},
            last_updated_time=datetime(2019, 6, 29, 0, 0, 0),
            issue_keys=[ndb.Key('FlakeIssue', 'chromium@123')])
    ]
    flake_issue = FlakeIssue.Create('chromium', 123)
    flake_issue.put()
    expected_disabled_test_dictionaries = [{
        'luci_project':
            'a',
        'normalized_step_name':
            'b',
        'normalized_test_name':
            'c',
        'disabled_test_variants': [
            [
                'os:Mac',
            ],
            [
                'Unknown',
            ],
        ],
        'issue_keys': [ndb.Key('FlakeIssue', 'chromium@123')],
        'issues': [{
            'issue_id':
                123,
            'issue_link':
                'https://monorail-prod.appspot.com/p/chromium/issues/detail?id=123',
        },],
        'tags': [],
        'disabled':
            True,
        'last_updated_time':
            datetime(2019, 6, 29, 0, 0, 0),
    }]
    self.assertEqual(
        expected_disabled_test_dictionaries,
        disabled_test_detection_utils.GenerateDisabledTestsData(disabled_tests))
