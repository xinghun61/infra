# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import json
import os
import unittest

from infra.libs.buildbot import master
from infra_libs.time_functions import timestamp
from infra_libs.utils import temporary_directory
from infra.services.master_manager_launcher import desired_state_parser
from testing_support import auto_stub


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


# UNIX timestamp corresponding to 500 seconds past epoch.
UNIX_TIMESTAMP_0500 = '1970-01-01T00:08:20Z'

UNIX_TIMESTAMP_1000 = '1970-01-01T00:16:40Z'

UNIX_TIMESTAMP_4000 = '1970-01-01T01:06:40Z'

UNIX_TIMESTAMP_5000 = '1970-01-01T01:23:20Z'

UNIX_TIMESTAMP_6000 = '1970-01-01T01:40:00Z'

UNIX_TIMESTAMP_7000 = '1970-01-01T01:56:40Z'

UNIX_TIMESTAMP_8000 = '1970-01-01T02:13:20Z'


class TestDesiredStateValidation(auto_stub.TestCase):
  def setUp(self):
    super(TestDesiredStateValidation, self).setUp()

    self.mock(timestamp, 'utcnow_ts', lambda: 5000)

  def _stateConfig(self, states, **params):
    c = {
        'version': desired_state_parser.VERSION,
        'master_states': {
          'master.chromium.fyi': states,
        },
    }
    if params:
      c['master_params'] = {
          'master.chromium.fyi': params,
      }
    return c


  def testValidState(self):
    desired_state_parser.validate_desired_master_state(self._stateConfig(
      [
        {'desired_state': 'running',
         'transition_time_utc': UNIX_TIMESTAMP_4000},
        {'desired_state': 'offline',
         'transition_time_utc': UNIX_TIMESTAMP_6000},
      ],
      drain_timeout_sec=1300,
      builder_filters=[
        r'^valid$',
      ],
    ))

  def testValidStateZulu(self):
    desired_state_parser.validate_desired_master_state(self._stateConfig([
        {'desired_state': 'running',
         'transition_time_utc': UNIX_TIMESTAMP_4000},
        {'desired_state': 'offline',
         'transition_time_utc': UNIX_TIMESTAMP_6000},
    ]))

  def testNoDesiredState(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
      ]))

  def testNoTransitionTime(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline'},
      ]))

  def testTransitionTimeInvalid(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'desired_state': 'running', 'transition_time_utc': 'boats'},
          {'desired_state': 'offline', 'transition_time_utc': 'llama'},
      ]))

  def testNotSorted(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
      ]))

  def testNotSortedZulu(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
      ]))

  def testInvalidState(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'desired_state': 'pajamas',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
      ]))

  def testUncertainPresent(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig([
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_8000},
      ]))

  def testUnknownKeyPresent(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig(
        [
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
        ],
        unknown_key=1337,
      ))

  def testNonNumericDrainTimeout(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig(
        [
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
        ],
        drain_timeout_sec='abc',
      ))

  def testInvalidBuilderFilter(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(self._stateConfig(
        [
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
        ],
        builder_filters=[
          r'+invalid-regex+',
        ],
      ))

  def testDifferentVersion(self):
    # Confirm that the configuration loads.
    c = self._stateConfig([
        {'desired_state': 'running',
         'transition_time_utc': UNIX_TIMESTAMP_4000},
        {'desired_state': 'offline',
         'transition_time_utc': UNIX_TIMESTAMP_6000},
    ])
    desired_state_parser.validate_desired_master_state(c)

    # Modify the version to invalidate it.
    c['version'] = 'test'
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.validate_desired_master_state(c)

  def testValidFile(self):
    desired_state_parser.load_desired_state_file(
        os.path.join(DATA_DIR, 'valid.json'))

  def testInvalidFile(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.load_desired_state_file(
          os.path.join(DATA_DIR, 'invalid.json'))

  def testBrokenFile(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      desired_state_parser.load_desired_state_file(
          os.path.join(DATA_DIR, 'broken.json'))


class TestMasterStateLookup(unittest.TestCase):
  STATE_CONFIG = [
      {'desired_state': 'pajamas', 'transition_time_utc': UNIX_TIMESTAMP_4000},
      {'desired_state': 'offline', 'transition_time_utc': UNIX_TIMESTAMP_6000},
  ]

  def testUnknownPast(self):
    state = desired_state_parser.get_master_state(self.STATE_CONFIG, now=300)
    self.assertIsNone(state)

  def testMiddle(self):
    state = desired_state_parser.get_master_state(self.STATE_CONFIG, now=4500)
    self.assertEqual(state, self.STATE_CONFIG[0])

  def testEnd(self):
    state = desired_state_parser.get_master_state(self.STATE_CONFIG, now=8000)
    self.assertEqual(state, self.STATE_CONFIG[1])


class TestHostnameLookup(auto_stub.TestCase):
  def setUp(self):
    super(TestHostnameLookup, self).setUp()

    self.mock(master, 'get_mastermap_for_host', lambda _x, _y: [
      {'dirname': 'master.chromium', 'internal': False},
      {'dirname': 'master.chromium.fyi', 'internal': False},
      {'dirname': 'master.supersecret', 'internal': True},
      {'dirname': 'master.ultrasecret', 'internal': True},
    ])


  def testHostnameLookup(self):
    """Test that selected masters are triggered and all else are ignored."""
    desired_state = {
        'version': desired_state_parser.VERSION,
        'master_states': {
          'master.chromium.fyi': [
            {'desired_state': 'running',
             'transition_time_utc': UNIX_TIMESTAMP_4000},
          ],
          'master.supersecret': [
            {'desired_state': 'running',
             'transition_time_utc': UNIX_TIMESTAMP_4000},
          ],
        },
        'master_params': {
          'master.chromium.fyi': {
            'drain_timeout_sec': 1337,
          },
        },
    }
    triggered, ignored = desired_state_parser.get_masters_for_host(
        desired_state,
        'bananas/',
        'impenetrablefortress.cool'
    )

    self.assertEqual(
        [t['dirname'] for t in triggered],
        ['master.chromium.fyi', 'master.supersecret'])
    self.assertEqual(ignored, set(['master.chromium', 'master.ultrasecret']))

    self.assertEqual(triggered[0]['params'], {
      'drain_timeout_sec': 1337,
    })
    self.assertEqual(triggered[1]['params'], {})

    self.assertEqual(sorted(ignored), [
      'master.chromium',
      'master.ultrasecret',
    ])

    for master_dict in triggered:
      self.assertIn(master_dict['dirname'], desired_state['master_states'])


class TestWritingState(auto_stub.TestCase):
  def setUp(self):
    super(TestWritingState, self).setUp()

    self.mock(timestamp, 'utcnow_ts', lambda: 5000)

  def testPruneOldEntries(self):
    with temporary_directory() as dirname:
      filename = os.path.join(dirname, 'desired_state.json')
      desired_state_parser.write_master_state({
        'master.chromium.fyi': [
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_0500},
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_1000},
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_7000},
      ]}, filename)

      with open(filename) as f:
        parsed_data = json.load(f)

      self.assertEqual(parsed_data, {
        'master.chromium.fyi': [
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_1000},
          {'desired_state': 'running',
           'transition_time_utc': UNIX_TIMESTAMP_4000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_6000},
          {'desired_state': 'offline',
           'transition_time_utc': UNIX_TIMESTAMP_7000},
        ]})

  def testInvalidState(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      with temporary_directory() as dirname:
        filename = os.path.join(dirname, 'desired_state.json')
        desired_state_parser.write_master_state({
          'master.chromium.fyi': [
            {'desired_state': 'running',
             'transition_time_utc': 'toast'},
            {'desired_state': 'running',
             'transition_time_utc': UNIX_TIMESTAMP_4000},
            {'desired_state': 'offline',
             'transition_time_utc': UNIX_TIMESTAMP_6000},
            {'desired_state': 'offline',
             'transition_time_utc': UNIX_TIMESTAMP_7000},
        ]}, filename)

  def testNothingInPast(self):
    with self.assertRaises(desired_state_parser.InvalidDesiredMasterState):
      with temporary_directory() as dirname:
        filename = os.path.join(dirname, 'desired_state.json')
        desired_state_parser.write_master_state({
          'master.chromium.fyi': [
            {'desired_state': 'offline',
             'transition_time_utc': UNIX_TIMESTAMP_6000},
            {'desired_state': 'offline',
             'transition_time_utc': UNIX_TIMESTAMP_7000},
        ]}, filename)

  def testNothing(self):
    with temporary_directory() as dirname:
      filename = os.path.join(dirname, 'desired_state.json')
      desired_state_parser.write_master_state({}, filename)

      with open(filename) as f:
        parsed_data = json.load(f)

      self.assertEqual(parsed_data, {})
