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
    super(UnsupportedClient, self).__init__(MOCK_REPOSITORY)
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
        _MockFindit(MOCK_REPOSITORY).RenamePlatform('linux'),
        'unix')

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
