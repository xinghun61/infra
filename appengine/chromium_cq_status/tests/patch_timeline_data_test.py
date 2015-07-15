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

class PatchTimelineDataTest(testing.AppengineTestCase):
  app_module = main.app

  def test_patch_timeline_data_simple(self):
    events = self._test_patch('real_patch_simple')
    self.assertEqual(events, [{
      'name': 'Attempt 1',
      'cat': 'Patch Progress',
      'ph': 'B',
      'ts': 1434395516000184,
      'pid': 'Attempt 1',
      'tid': 'Patch Progress',
      'cname': 'cq_build_attempt_running',
      'args': {},
    }, {
      'name': 'Test-Trybot',
      'cat': 'client.skia.fyi',
      'ph': 'B',
      'ts': 1434395520503088,
      'pid': 'Attempt 1',
      'tid': 'Test-Trybot',
      'cname': 'cq_build_running',
      'args': {},
    }, {
      'name': 'Test-Trybot',
      'cat': 'client.skia.fyi',
      'ph': 'E',
      'ts': 1434395577891760,
      'pid': 'Attempt 1',
      'tid': 'Test-Trybot',
      'cname': 'cq_build_passed',
      'args': {
        'build_url': ('http://build.chromium.org/p/client.skia.fyi/builders/'
                      'Test-Trybot/builds/794'),
      },
    }, {
      'name': 'Patch Committing',
      'cat': 'Patch Progress',
      'ph': 'B',
      'ts': 1434395579639639,
      'pid': 'Attempt 1',
      'tid': 'Patch Progress',
      'cname': 'cq_build_attempt_running',
      'args': {},
    }, {
      'name': 'Patch Committing',
      'cat': 'Patch Progress',
      'ph': 'E',
      'ts': 1434395584564138,
      'pid': 'Attempt 1',
      'tid': 'Patch Progress',
      'cname': 'cq_build_attempt_passed',
      'args': {},
    }, {
      'name': 'Attempt 1',
      'cat': 'Patch Progress',
      'ph': 'E',
      'ts': 1434395584564362,
      'pid': 'Attempt 1',
      'tid': 'Patch Progress',
      'cname': 'cq_build_attempt_passed',
      'args': {
        'action': 'patch_stop',
      },
    }])

  def test_patch_timeline_data_multiple_attempts(self):
    events = self._test_patch('real_patch_multiple_attempts')
    self.assertNotEqual(0, len(events))
    bCount = 0
    eCount = 0
    for event in events:
      self.assertTrue(re.match('Attempt \d+', event.get('pid')))
      self.assertNotEqual(None, event.get('ts'))
      if re.match('Attempt \d+', event.get('name')):
        # Patch Progress bar
        self.assertEqual(event.get('name'), event.get('pid'))
        self.assertEqual('Patch Progress', event.get('tid'))
      elif re.match('test_presubmit', event.get('name')):
        # Builder bar
        self.assertEqual('test_presubmit', event.get('tid'))
      else:
        # Committing Progress
        self.assertEqual('Patch Committing', event.get('name'))
        self.assertEqual('Patch Progress', event.get('tid'))
      if event.get('ph') == 'B':
        bCount += 1
      if event.get('ph') == 'E':
        eCount += 1
    self.assertEquals(bCount, eCount)

  def test_patch_timeline_increasing_timestamps(self):
    events = self._test_patch('real_patch_multiple_attempts')
    self.assertNotEqual(0, len(events))
    previous_ts = events[0].get('ts')
    for event in events:
      self.assertTrue(previous_ts <= event.get('ts'))
      previous_ts = event.get('ts')

  def test_patch_timeline_data_cq_buggy(self):
    events = self._test_patch('patch_cq_buggy')
    self.assertNotEqual(0, len(events))
    for event in events:
      self.assertTrue(re.match('Attempt \d+', event.get('pid')))
      self.assertNotEqual(None, event.get('ts'))
      if re.match('Attempt \d+', event.get('name')):
        # Patch Progress bar
        self.assertEqual(event.get('name'), event.get('pid'))
        self.assertEqual('Patch Progress', event.get('tid'))
      elif re.match('Test-Trybot', event.get('name')):
        # Builder bar
        self.assertEqual('Test-Trybot', event.get('tid'))
        self.assertEqual('I', event.get('ph'))
      else:
        # Committing Progress
        self.assertEqual('Patch Committing', event.get('name'))
        self.assertEqual('Patch Progress', event.get('tid'))

  def test_patch_timeline_data_failed(self):
    events = self._test_patch('patch_failed')
    self.assertNotEqual(0, len(events))
    bCount = 0
    eCount = 0
    for event in events:
      self.assertTrue(re.match('Attempt \d+', event.get('pid')))
      self.assertNotEqual(None, event.get('ts'))
      if re.match('Attempt \d+', event.get('name')):
        # Patch Progress bar
        self.assertEqual(event.get('name'), event.get('pid'))
        self.assertEqual('Patch Progress', event.get('tid'))
      else:
        # There should be no commits on failure.
        self.assertNotEqual('Patch Committing', event.get('name'))
      # Don't check builders because multiples are used.
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
    response = self.test_app.get(
        '/patch-timeline-data/%s/%s' % (issue, patchset))
    summary = json.loads(response.body)
    logging.debug(json.dumps(summary, indent=2))
    return summary


def _load_json(filename):
  path = os.path.join(os.path.dirname(__file__), 'resources', filename)
  return json.loads(open(path).read())
