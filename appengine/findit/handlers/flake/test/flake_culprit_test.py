# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import webapp2

from testing_utils import testing

from handlers.flake import flake_culprit
from libs import analysis_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis


class FlakeCulpritTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/flake-culprit', flake_culprit.FlakeCulprit),
      ], debug=True)

  def testConvertAnalysisToDict(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.confidence_in_culprit = 0.9
    analysis.put()
    expected_result = {
        'master_name': master_name,
        'builder_name': builder_name,
        'step_name': step_name,
        'test_name': test_name,
        'key': analysis.key.urlsafe(),
        'confidence_in_culprit': 0.9,
    }

    self.assertEqual(
        expected_result,
        flake_culprit._ConvertAnalysisToDict(analysis.key.urlsafe()))

  def testGetFlakeAnalysesAsDicts(self):
    analysis1 = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't1')
    analysis1.confidence_in_culprit = 0.3
    analysis1.put()
    analysis2 = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't2')
    analysis2.confidence_in_culprit = 0.8
    analysis2.put()
    culprit = FlakeCulprit.Create('repo', 'revision', 1000)
    culprit.flake_analysis_urlsafe_keys = [
        analysis1.key.urlsafe(),
        analysis2.key.urlsafe()
    ]

    expected_result = [{
        'master_name': 'm',
        'builder_name': 'b',
        'step_name': 's',
        'test_name': 't1',
        'key': analysis1.key.urlsafe(),
        'confidence_in_culprit': 0.3,
    }, {
        'master_name': 'm',
        'builder_name': 'b',
        'step_name': 's',
        'test_name': 't2',
        'key': analysis2.key.urlsafe(),
        'confidence_in_culprit': 0.8,
    }]

    self.assertEqual(expected_result,
                     flake_culprit._GetFlakeAnalysesAsDicts(culprit))

  def testGetCulpritSuccess(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.confidence_in_culprit = 0.7
    analysis.put()
    culprit = FlakeCulprit.Create('chromium', 'r1', 1000)
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.cr_notification_status = analysis_status.COMPLETED
    culprit.cr_notification_time = datetime(2017, 07, 19, 10, 03, 00)
    culprit.put()

    expected_result = {
        'project_name':
            'chromium',
        'revision':
            'r1',
        'commit_position':
            1000,
        'cr_notified':
            True,
        'cr_notification_time':
            '2017-07-19 10:03:00 UTC',
        'analyses': [{
            'master_name': 'm',
            'builder_name': 'b',
            'step_name': 's',
            'test_name': 't',
            'key': analysis.key.urlsafe(),
            'confidence_in_culprit': 0.7,
        }],
        'key':
            culprit.key.urlsafe(),
    }

    response = self.test_app.get(
        '/flake/flake-culprit?key=%s&format=json' % culprit.key.urlsafe())
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body)

  def testGetCulpritError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.put()
    culprit = FlakeCulprit.Create('chromium', 'r1', 1000)
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.cr_notification_status = analysis_status.COMPLETED
    culprit.cr_notification_time = datetime(2017, 07, 19, 10, 03, 00)

    response = self.test_app.get(
        '/flake/flake-culprit',
        params={
            'key': culprit.key.urlsafe(),
            'format': 'json',
        },
        status=404)

    self.assertEqual('Culprit not found!',
                     response.json_body.get('error_message'))
