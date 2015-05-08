# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from infra.libs.buildbot import master
from infra.libs.time_functions import timestamp
from infra.services.master_manager_launcher import desired_state_parser
from testing_support import auto_stub


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


class TestDesiredStateValidation(auto_stub.TestCase):
  def setUp(self):
    super(TestDesiredStateValidation, self).setUp()

    self.mock(timestamp, 'utcnow_ts', lambda: 5000)

  def testValidState(self):
    self.assertTrue(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'desired_state': 'running', 'transition_time_utc': 4000},
        {'desired_state': 'offline', 'transition_time_utc': 6000},
    ]}))

  def testNoDesiredState(self):
    self.assertFalse(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'transition_time_utc': 4000},
        {'desired_state': 'offline', 'transition_time_utc': 6000},
    ]}))

  def testNoTransitionTime(self):
    self.assertFalse(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'desired_state': 'running', 'transition_time_utc': 4000},
        {'desired_state': 'offline'},
    ]}))

  def testTransitionTimeInvalid(self):
    self.assertFalse(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'desired_state': 'running', 'transition_time_utc': 'boats'},
        {'desired_state': 'offline', 'transition_time_utc': 'llama'},
    ]}))

  def testNotSorted(self):
    self.assertFalse(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'desired_state': 'offline', 'transition_time_utc': 6000},
        {'desired_state': 'running', 'transition_time_utc': 4000},
    ]}))

  def testInvalidState(self):
    self.assertFalse(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'desired_state': 'pajamas', 'transition_time_utc': 4000},
        {'desired_state': 'offline', 'transition_time_utc': 6000},
    ]}))

  def testUncertainPresent(self):
    self.assertFalse(desired_state_parser.desired_master_state_is_valid({
      'master.chromium.fyi': [
        {'desired_state': 'running', 'transition_time_utc': 6000},
        {'desired_state': 'offline', 'transition_time_utc': 8000},
    ]}))

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
  STATES = [
        {'desired_state': 'pajamas', 'transition_time_utc': 4000},
        {'desired_state': 'offline', 'transition_time_utc': 6000},
  ]

  def testUnknownPast(self):
    state = desired_state_parser.get_master_state(self.STATES, now=300)
    self.assertIsNone(state)

  def testMiddle(self):
    state = desired_state_parser.get_master_state(self.STATES, now=4500)
    self.assertEqual(state, self.STATES[0])

  def testEnd(self):
    state = desired_state_parser.get_master_state(self.STATES, now=8000)
    self.assertEqual(state, self.STATES[1])


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
        'master.chromium.fyi': [
          {'desired_state': 'running', 'transition_time_utc': 4000},
        ],
        'master.supersecret': [
          {'desired_state': 'running', 'transition_time_utc': 4000},
        ],
    }
    triggered, ignored = desired_state_parser.get_masters_for_host(
        desired_state,
        'bananas/',
        'impenetrablefortress.cool'
    )

    self.assertEqual(len(triggered), 2)
    self.assertEqual(len(ignored), 2)

    self.assertEqual(sorted(ignored), [
      'master.chromium',
      'master.ultrasecret',
    ])

    for master_dict in triggered:
      self.assertIn(master_dict['dirname'], desired_state)
