# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import logging

from google.appengine.api import app_identity

from crash.type_enums import CrashClient
from crash.test.predator_testcase import PredatorTestCase
from libs import analysis_status
from model.crash.cracas_crash_analysis import CracasCrashAnalysis
from model.crash.crash_analysis import CrashAnalysis


class FinditTest(PredatorTestCase):

  def setUp(self):
    super(FinditTest, self).setUp()
    self.findit = self.GetMockFindit(client_id=CrashClient.FRACAS)

  def testPlatformRename(self):
    self.assertEqual(self.findit.RenamePlatform('linux'), 'unix')

  def testCheckPolicyNoneClientConfig(self):
    unsupported_client = self.GetMockFindit(client_id='unconfiged')
    crash_data = unsupported_client.GetCrashData(
        self.GetDummyChromeCrashData(
            platform = 'canary',
            signature = 'sig',
        ))
    self.assertTrue(unsupported_client._CheckPolicy(crash_data))

  def testCheckPolicyNoBlackList(self):
    """Tests ``_CheckPolicy`` method with no black list configured."""
    crash_data = self.findit.GetCrashData(self.GetDummyChromeCrashData())
    self.assertTrue(self.findit._CheckPolicy(crash_data))

  def testCheckPolicyWithBlackList(self):
    """Tests ``_CheckPolicy`` return false if signature is blacklisted."""
    crash_data = self.findit.GetCrashData(self.GetDummyChromeCrashData(
        client_id=CrashClient.FRACAS,
        signature='Blacklist marker signature'))
    self.assertFalse(self.findit._CheckPolicy(crash_data))

  def testDoesNotNeedNewAnalysisIfCheckPolicyFailed(self):
    """Tests that ``NeedsNewAnalysis`` returns False if policy check failed."""
    raw_crash_data = self.GetDummyChromeCrashData(
        client_id=CrashClient.FRACAS,
        signature='Blacklist marker signature')
    crash_data = self.findit.GetCrashData(raw_crash_data)
    self.assertFalse(self.findit.NeedsNewAnalysis(crash_data))

  def testDoesNotNeedNewAnalysisIfCrashAnalyzedBefore(self):
    """Tests that ``NeedsNewAnalysis`` returns False if crash analyzed."""
    crash_data = self.findit.GetCrashData(self.GetDummyChromeCrashData())
    crash_analysis_model = self.findit.CreateAnalysis(crash_data.identifiers)
    crash_analysis_model.regression_range = crash_data.regression_range
    crash_analysis_model.put()
    self.assertFalse(self.findit.NeedsNewAnalysis(crash_data))

  def testNeedsNewAnalysisIfNoAnalysisYet(self):
    """Tests that ``NeedsNewAnalysis`` returns True if crash not analyzed."""
    crash_data = self.findit.GetCrashData(self.GetDummyChromeCrashData())
    self.mock(CrashAnalysis, 'Initialize', lambda *_: None)
    self.assertTrue(self.findit.NeedsNewAnalysis(crash_data))

  def testNeedsNewAnalysisIfLastOneFailed(self):
    """Tests that ``NeedsNewAnalysis`` returns True if last analysis failed."""
    crash_data = self.findit.GetCrashData(self.GetDummyChromeCrashData())
    crash_analysis_model = self.findit.CreateAnalysis(crash_data.identifiers)
    crash_analysis_model.status = analysis_status.ERROR
    crash_analysis_model.put()
    self.mock(CrashAnalysis, 'Initialize', lambda *_: None)
    self.assertTrue(self.findit.NeedsNewAnalysis(crash_data))

  def testGetPublishableResultFoundTrue(self):
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reasons': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }

    processed_analysis_result = copy.deepcopy(analysis_result)
    for cl in processed_analysis_result['suspected_cls']:
      cl['confidence'] = round(cl['confidence'], 2)
      cl.pop('reasons', None)

    crash_identifiers = {'signature': 'sig'}
    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.findit.client_id,
        'result': processed_analysis_result,
    }

    analysis = CracasCrashAnalysis.Create(crash_identifiers)
    analysis.result = analysis_result

    self.assertDictEqual(self.findit.GetPublishableResult(crash_identifiers,
                                                          analysis),
                         expected_processed_result)

  def testGetPublishableResultFoundFalse(self):
    analysis_result = {
        'found': False,
    }
    crash_identifiers = {'signature': 'sig'}
    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self.findit.client_id,
        'result': copy.deepcopy(analysis_result),
    }

    analysis = CracasCrashAnalysis.Create(crash_identifiers)
    analysis.result = analysis_result

    self.assertDictEqual(self.findit.GetPublishableResult(crash_identifiers,
                                                          analysis),
                         expected_processed_result)
