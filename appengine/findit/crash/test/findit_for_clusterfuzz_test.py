# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from crash import chromecrash_parser
from crash import detect_regression_range
from crash import findit
from crash import findit_for_chromecrash
from crash.clusterfuzz_parser import ClusterfuzzParser
from crash.crash_report import CrashReport
from crash.culprit import Culprit
from crash.findit_for_clusterfuzz import FinditForClusterfuzz
from crash.loglinear.changelist_classifier import LogLinearChangelistClassifier
from crash.suspect import Suspect
from crash.stacktrace import CallStack
from crash.stacktrace import Stacktrace
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs.deps import chrome_dependency_fetcher
from libs.gitiles.gitiles_repository import GitilesRepository
from model import analysis_status
from model.crash.crash_analysis import CrashAnalysis
from model.crash.crash_config import CrashConfig
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FinditForClusterfuzzTest(PredatorTestCase):

  def setUp(self):
    super(FinditForClusterfuzzTest, self).setUp()
    self._client = FinditForClusterfuzz(self.GetMockRepoFactory(),
                                        CrashConfig.Get())

  def testCheckPolicy(self):
    crash_data = self._client.GetCrashData(self.GetDummyClusterfuzzData(
        client_id = CrashClient.CLUSTERFUZZ))
    self.assertTrue(self._client._CheckPolicy(crash_data))

  def testCreateAnalysis(self):
    self.assertIsNotNone(self._client.CreateAnalysis({'testcase': '341335434'}))

  def testGetAnalysis(self):
    crash_identifiers = {'testcase': '341335434'}
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.put()
    self.assertEqual(self._client.GetAnalysis(crash_identifiers), analysis)
