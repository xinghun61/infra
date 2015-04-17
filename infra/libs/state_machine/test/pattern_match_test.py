# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.libs.state_machine import pattern_match


TEST_STATESPACE = {
    'cars': [
      'cars_coming_close',
      'cars_coming_far_away',
      'no_cars',
    ],
    'walk_sign': [
      'dont_walk',
      'walk',
    ],
    'corgs': [  # Don't jaywalk in front of a corg!
      'corgs',
      'no_corgs',
    ],
}


class TestStateMachinePatternMatch(unittest.TestCase):
  # There is a bug in pylint which triggers false positives on decorated
  # decorators with arguments: http://goo.gl/Ln6uyn
  # pylint: disable=no-value-for-parameter
  def setUp(self):
    self.matchlist = pattern_match.MatchList(TEST_STATESPACE)
    super(TestStateMachinePatternMatch, self).setUp()

  def testInvlidState(self):
    with self.assertRaises(AssertionError):
      @self.matchlist.add_match(
          corgs='no_cars')
      def _dummy():  # pragma: no cover
        return None

  def testInvalidValue(self):
    with self.assertRaises(AssertionError):
      @self.matchlist.add_match(
          cars='no_corgs')
      def _dummy():  # pragma: no cover
        return None

  def testInvalidDetector(self):
    with self.assertRaises(AssertionError):
      @self.matchlist.add_detector('cargs')
      def _fake_check_for_corgs(_data):  # pragma: no cover
        return 'no_corgs'

  def testSuccessfulConstruction(self):
    self._construct_matchlist()
    self.assertTrue(self.matchlist.is_correct)

    execution_list = self.matchlist.execution_list({
      'walk_sign_walking_person': False,
      'corgs_east': False,
      'corgs_west': False,
      'near_cars': True,
      'far_cars': False,
    })
    self.assertEqual(execution_list,
        (
          {
            'cars': 'cars_coming_close',
            'corgs': 'no_corgs',
            'walk_sign': 'dont_walk',
          },
          '_dont_walk',
          ['dont_walk'],
        )
    )

  def testIdempotentTrue(self):
    self._construct_matchlist()
    self.assertTrue(self.matchlist.is_correct)
    self.assertTrue(self.matchlist.is_correct)

  def testIdempotentFalse(self):
    self._construct_matchlist(under_match=True)
    self.assertFalse(self.matchlist.is_correct)
    self.assertFalse(self.matchlist.is_correct)

  def testGetMatches(self):
    self._construct_matchlist()
    self.matchlist._get_matches()

  def testRunBeforeCheck(self):
    with self.assertRaises(AssertionError):
      self.matchlist.print_all_states()

  def testAddAfterCheck(self):
    self._construct_matchlist()
    self.assertTrue(self.matchlist.is_correct)
    with self.assertRaises(AssertionError):
      @self.matchlist.add_match(
          cars='no_cars',
          exclusions={'corgs': ['corgs']})
      def _walk():  # pragma: no cover
        return ['walk']

  def testUnderDescribed(self):
    # This removes the cars='no_cars' -> walk match.
    self._construct_matchlist(under_match=True)
    self.assertFalse(self.matchlist.is_correct)

  def testDetectorReturnsWeirdValue(self):
    self._construct_matchlist(under_detect=True)

    @self.matchlist.add_detector('corgs')
    def _check_for_corgs(data):  # pragma: no cover
      if data.get('corgs_east') or data.get('corgs_west'):
        return 'borgs'  # Not a valid state.
      return 'borgs'

    with self.assertRaises(AssertionError):
      self.matchlist.execution_list({
        'walk_sign_walking_person': False,
        'corgs_east': False,
        'corgs_west': False,
        'near_cars': True,
        'far_cars': False,
      })

  def testCallsIsCorrectAutomatically(self):
    self._construct_matchlist()

    self.matchlist.execution_list({
      'walk_sign_walking_person': False,
      'corgs_east': False,
      'corgs_west': False,
      'near_cars': True,
      'far_cars': False,
    })

  def testCallWithMissingData(self):
    self._construct_matchlist()

    self.matchlist.execution_list({})

  def testOverDescribed(self):
    # This doubles up on the cars='no_cars' match.
    self._construct_matchlist()
    @self.matchlist.add_match(
        cars='no_cars',
        exclusions={'corgs': ['corgs']})
    def _walk():  # pragma: no cover
      return ['walk']
    self.assertFalse(self.matchlist.is_correct)

  def testUnderDetect(self):
    # Leaves off corg detector.
    self._construct_matchlist(under_detect=True)
    self.assertFalse(self.matchlist.is_correct)

  def testOverDetect(self):
    # Leaves off corg detector.
    self._construct_matchlist()

    with self.assertRaises(AssertionError):
      @self.matchlist.add_detector('cargs')
      def _check_for_corgs(data):  # pragma: no cover
        if data.get('corgs_east') or data.get('corgs_west'):
          return 'corgs'
        return 'no_corgs'

  def _construct_matchlist(self, under_match=False, under_detect=False):
    # Shims to selectively underdefine matches or detectors.
    selective_match = {
        'cars': 'no_cars',
        'exclusions': {'corgs': ['corgs']},
    }
    if under_match:
      # Underdefine the matchlist.
      selective_match = {}

    @self.matchlist.add_match(**selective_match)
    @self.matchlist.add_match(
        cars='cars_coming_far_away',
        walk_sign='dont_walk',
        corgs='no_corgs')
    @self.matchlist.add_match(
        walk_sign='walk')
    def _walk():  # pragma: no cover
      return ['walk']

    @self.matchlist.add_match(
        walk_sign='dont_walk',
        corgs='corgs')
    @self.matchlist.add_match(
        cars='cars_coming_close',
        exclusions={'walk_sign': ['walk']})
    def _dont_walk():
      return ['dont_walk']

    @self.matchlist.add_detector('cars')
    def _check_for_cars(data):
      if data.get('near_cars'):
        return 'cars_coming_close'
      if data.get('far_cars'):  # pragma: no cover
        return 'cars_coming_far_away'
      return 'no_cars'  # pragma: no cover

    @self.matchlist.add_detector('walk_sign')
    def _check_sign(data):
      if data.get('walk_sign_walking_person'):
        return 'walk'  # pragma: no cover
      return 'dont_walk'

    if not under_detect:
      # Correctly detect all states, otherwise underdetect by leaving this out.
      @self.matchlist.add_detector('corgs')
      def _check_for_corgs(data):
        if data.get('corgs_east') or data.get('corgs_west'):
          return 'corgs'  # pragma: no cover
        return 'no_corgs'
