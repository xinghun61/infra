# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import webapp2

from handlers.flake.detection import show_flake
from model.flake.detection.flake import Flake
from model.flake.detection.flake_issue import FlakeIssue
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

  def testShowFlake(self):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time = datetime.datetime(2018, 1, 1)
    flake_issue.put()

    luci_project = 'chromium'
    step_name = 'step'
    test_name = 'test'
    normalized_step_name = Flake.NormalizeStepName(step_name)
    normalized_test_name = Flake.NormalizeTestName(test_name)
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name)

    flake.flake_issue_key = flake_issue.key
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    reference_succeeded_build_id = 456
    time_happened = datetime.datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = CQFalseRejectionFlakeOccurrence.Create(
        build_id=build_id,
        step_name=step_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        reference_succeeded_build_id=reference_succeeded_build_id,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.put()

    response = self.test_app.get(
        '/flake/detection/ui/show-flake',
        params={
            'key': flake.key.urlsafe(),
            'format': 'json',
        },
        status=200)

    flake_dict = flake.to_dict()
    flake_dict['occurrences'] = [occurrence.to_dict()]
    flake_dict['flake_issue'] = flake_issue.to_dict()
    flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        flake_issue.monorail_project, flake_issue.issue_id)

    # TODO(crbug.com/864426): Polymer renders int64 type to a random number in
    # html template variable replacement, and this is causing all the link on
    # flake detection frontend page to point to 404, so convert int64 to str to
    # work this around. Remove the hack once the bug is fixed.
    for occurrence in flake_dict['occurrences']:
      occurrence['build_id'] = str(occurrence['build_id'])
      occurrence['reference_succeeded_build_id'] = str(
          occurrence['reference_succeeded_build_id'])

    self.assertEqual(
        json.dumps({
            'flake_json': flake_dict
        }, default=str), response.body)
