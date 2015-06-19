# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import logging
import os
import re

import main
from model.record import Record
from tests.testing_utils import testing

class PatchTimelineTest(testing.AppengineTestCase):
  app_module = main.app

  def test_patch_timeline_simple(self):
    events = self._test_patch('real_patch_simple')
    self.assertEqual(events, [{
      'name': 'Attempt 1',
      'cat': 'Patch Progress',
      'ph': 'B',
      'ts': 1434395516.000184,
      'pid': 'Attempt 1',
      'tid': 'Patch Progress',
      'args': {},
    }, {
      'name': 'Test-Trybot',
      'cat': 'client.skia.fyi',
      'ph': 'B',
      'ts': 1434395520.503088,
      'pid': 'Attempt 1',
      'tid': 'Test-Trybot',
      'args': {},
    }, {
      'name': 'Test-Trybot',
      'cat': 'client.skia.fyi',
      'ph': 'E',
      'ts': 1434395577.89176,
      'pid': 'Attempt 1',
      'tid': 'Test-Trybot',
      'args': {
        'build_url': ('http://build.chromium.org/p/client.skia.fyi/builders/'
                      'Test-Trybot/builds/794'),
      },
    }, {
      'name': 'Attempt 1',
      'cat': 'Patch Progress',
      'ph': 'E',
      'ts': 1434395584.564362,
      'pid': 'Attempt 1',
      'tid': 'Patch Progress',
      'args': {},
    }])

  def test_patch_timeline_multiple_attempts(self):
    events = self._test_patch('real_patch_multiple_attempts')
    self.assertNotEqual(0, len(events))
    bCount = 0
    eCount = 0
    for event in events:
      # check if it's a patch progress bar
      if re.match('Attempt \d+', event.get('name')):
        self.assertEqual(event.get('name'), event.get('pid'))
        self.assertEqual('Patch Progress', event.get('tid'))
        self.assertNotEqual(None, event.get('ts'))
      else:
        self.assertTrue(re.match('Attempt \d+', event.get('pid')))
        self.assertEqual('test_presubmit', event.get('tid'))
        self.assertEqual('test_presubmit', event.get('name'))
        self.assertNotEqual(None, event.get('ts'))
      if event.get('ph') == 'B':
        bCount += 1
      if event.get('ph') == 'E':
        eCount += 1
    self.assertEquals(bCount, eCount)

  def _load_records(self, filename):
    assert Record.query().count() == 0
    records = _load_json(filename)
    for record in records:
      self.mock_now(datetime.utcfromtimestamp(record['timestamp']))
      Record(
        id=record['key'],
        tags=record['tags'],
        fields=record['fields'],
      ).put()

  def _test_patch(self, name, issue=123456789, patchset=1):
    self._load_records('%s.json' % name)
    response = self.test_app.get('/patch-timeline/%s/%s' % (issue, patchset))
    summary = json.loads(response.body)
    logging.debug(json.dumps(summary, indent=2))
    return summary


def _load_json(filename):
  path = os.path.join(os.path.dirname(__file__), 'resources', filename)
  return json.loads(open(path).read())
