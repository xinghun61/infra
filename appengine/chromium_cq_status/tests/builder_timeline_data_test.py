# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import json
import main

from tests.testing_utils import testing
from handlers.builder_timeline_data import create_events

class BuilderTimelineDataTest(testing.AppengineTestCase):
  app_module = main.app

  def test_simple_data(self):
    data = load_json('builder_simple.json')
    master = 'tryserver'
    builder = 'test builder'
    buildId = 1
    attempt_string = 'Attempt 1'
    events = create_events(data, master, builder, buildId, attempt_string)
    bCount = 0
    eCount = 0
    for event in events:
      self.assertEqual(master, event.cat)
      self.assertEqual(builder, event.tid)
      self.assertEqual(attempt_string, event.pid)
      self.assertEqual(buildId, event.args['id'])
      if event.ph == 'B':
        bCount += 1
      if event.ph == 'E':
        eCount += 1
    self.assertEqual(bCount, eCount)
  
def load_json(filename):
  path = os.path.join(os.path.dirname(__file__), 'resources', filename)
  return json.loads(open(path).read())
