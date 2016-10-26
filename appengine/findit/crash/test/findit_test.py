# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import logging

from crash.findit import Findit
from crash.type_enums import CrashClient
from crash.test.crash_pipeline_test import DummyCrashData
from crash.test.crash_testcase import CrashTestCase
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

# In production we'd use CrashWrapperPipeline. And that'd work fine here,
# since we never actually call the method that uses it. But just to be
# absolutely sure we don't go over the wire due to some mocking failure,
# we'll use this dummy class instead. (In fact, since it's never used,
# we don't even need to give a real class; |None| works just fine.)
MOCK_PIPELINE_CLS = None

MOCK_REPOSITORY = None

class UnsupportedClient(Findit): # pylint: disable=W0223
  # TODO(http://crbug.com/659346): this isn't being called for some reason.
  @property
  def client_id(self): # pragma: no cover
    return self._client_id

  @property
  def config(self): # pragma: no cover
    """Don't return None, so that PlatformRename doesn't crash."""
    return {}

  def __init__(self, client_id=None):
    super(UnsupportedClient, self).__init__(MOCK_REPOSITORY, MOCK_PIPELINE_CLS)
    if client_id is None:
      client_id = 'unsupported_client'
    self._client_id = client_id


class FinditTest(CrashTestCase):

  def testPlatformRename(self):
    class _MockFindit(Findit): # pylint: disable=W0223
      @classmethod
      def _ClientID(cls):
        return CrashClient.FRACAS

    self.assertEqual(
        _MockFindit(MOCK_REPOSITORY, MOCK_PIPELINE_CLS).RenamePlatform('linux'),
        'unix')

  def testScheduleNewAnalysisWithFailingPolicy(self):
    class _MockFindit(Findit): # pylint: disable=W0223
      def __init__(self):
        super(_MockFindit, self).__init__(MOCK_REPOSITORY, MOCK_PIPELINE_CLS)

      def CheckPolicy(self, crash_data):
        """This is the same as inherited, but just to be explicit."""
        return None

      def _NeedsNewAnalysis(self, _crash_data):
        raise AssertionError('testScheduleNewAnalysisWithFailingPolicy: '
            "called _MockFindit._NeedsNewAnalysis, when it shouldn't.")

    self.assertFalse(_MockFindit().ScheduleNewAnalysis(DummyCrashData()))

  def testScheduleNewAnalysisWithPlatformRename(self):
    original_crash_data = DummyCrashData(
        version = None,
        platform = 'unix',
        crash_identifiers = {})
    renamed_crash_data = copy.deepcopy(original_crash_data)
    renamed_crash_data['platform'] = 'linux'

    testcase = self
    class _MockFindit(Findit): # pylint: disable=W0223
      def __init__(self):
        super(_MockFindit, self).__init__(MOCK_REPOSITORY, MOCK_PIPELINE_CLS)

      @property
      def config(self):
        """Make PlatformRename work as expected."""
        return {'platform_rename': {'unix': 'linux'}}

      def CheckPolicy(self, crash_data):
        """Call PlatformRename, and return successfully.

        N.B., if we did not override this method, then our overridden
        ``_NeedsNewAnalysis`` would never be called either."""
        # TODO(wrengr): should we clone |crash_data| rather than mutating it?
        crash_data['platform'] = self.RenamePlatform(crash_data['platform'])
        return crash_data

      def _NeedsNewAnalysis(self, new_crash_data):
        logging.debug('Called _MockFindit._NeedsNewAnalysis, as desired')
        testcase.assertDictEqual(new_crash_data, renamed_crash_data)
        return False

    self.assertFalse(_MockFindit().ScheduleNewAnalysis(original_crash_data))

  def testCheckPolicyUnsupportedClient(self):
    self.assertIsNone(UnsupportedClient().CheckPolicy(DummyCrashData(
        platform = 'canary',
        signature = 'sig',
    )))

  def testCreateAnalysisForUnsupportedClientId(self):
    self.assertIsNone(UnsupportedClient('unsupported_id').CreateAnalysis(
        {'signature': 'sig'}))

  def testGetAnalysisForUnsuportedClient(self):
    crash_identifiers = {'signature': 'sig'}
    # TODO(wrengr): it'd be less fragile to call FinditForFracas.CreateAnalysis
    # instead. But then we'd need to make UnsupportedClient inherit that
    # implementation, rather than inheriting the one from the Findit
    # base class.
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.put()
    self.assertIsNone(
        UnsupportedClient('Unsupported_client').GetAnalysis(crash_identifiers),
        'Unsupported client unexpectedly got analysis %s via identifiers %s'
        % (analysis, crash_identifiers))
