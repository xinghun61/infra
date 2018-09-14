# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import webapp2

from handlers.flake.detection import rank_flakes
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from waterfall.test.wf_testcase import WaterfallTestCase


class RankFlakesTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/ui/rank-flakes', rank_flakes.RankFlakes),
      ],
      debug=True)

  def testRankFlakes(self):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time = datetime.datetime(2018, 1, 1)
    flake_issue.put()

    luci_project = 'chromium'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    flake1 = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=normalized_test_name)

    flake1.flake_issue_key = flake_issue.key
    flake1.false_rejection_count_last_week = 2
    flake1.impacted_cl_count_last_week = 2
    flake1.put()

    flake2 = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name='another_test',
        test_label_name='another_test')
    flake2.put()

    flake3 = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name='another_test',
        test_label_name='another_test')
    flake3.false_rejection_count_last_week = 5
    flake3.impacted_cl_count_last_week = 2
    flake3.put()

    response = self.test_app.get(
        '/flake/detection/ui/rank-flakes',
        params={
            'format': 'json',
        },
        status=200)

    flake1_dict = flake1.to_dict()
    flake1_dict['flake_urlsafe_key'] = flake1.key.urlsafe()
    flake1_dict['flake_issue'] = flake_issue.to_dict()
    flake1_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        flake_issue.monorail_project, flake_issue.issue_id)

    flake3_dict = flake3.to_dict()
    flake3_dict['flake_urlsafe_key'] = flake3.key.urlsafe()

    self.assertEqual(
        json.dumps({
            'flakes_data': [flake3_dict, flake1_dict],
            'luci_project': ''
        }, default=str), response.body)
