# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import webapp2

from google.appengine.api import users

from handlers.flake.detection import test_flake
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.detection.flake_occurrence import FlakeType
from waterfall.test.wf_testcase import WaterfallTestCase


class TestFlakeTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/flake/detection/ui/test-flake', test_flake.TestFlake),
      ], debug=True)

  def testResponse(self):
    step_name = 's'
    test_name = 't'
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build_id = 100
    time_reported = datetime.datetime(2018, 1, 1)
    flake_type = FlakeType.OUTRIGHT_FLAKE

    # Create the parent flake.
    flake = Flake.Create(step_name, test_name)
    flake.put()

    # Put the occurrence under it.
    occurrence = FlakeOccurrence.Create(
        step_name=step_name,
        test_name=test_name,
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number,
        build_id=build_id,
        time_reported=time_reported,
        flake_type=flake_type)
    occurrence.put()

    response = self.test_app.get(
        '/flake/detection/ui/test-flake',
        params={
            'key': flake.key.urlsafe(),
            'format': 'json',
        },
        status=200)

    flake_dict = flake.to_dict()
    flake_dict['occurrences'] = [occurrence.to_dict()]
    self.assertEqual(
        json.dumps({
            'flake_json': flake_dict
        }, default=str), response.body)

  def testResponseNoKey(self):
    response = self.test_app.get(
        '/flake/detection/ui/test-flake',
        params={
            'format': 'json',
        },
        status=500)
    self.assertEqual('Key is a required parameter.',
                     response.json_body.get('error_message'))
