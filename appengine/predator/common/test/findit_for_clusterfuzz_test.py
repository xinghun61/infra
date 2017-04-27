# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis import chromecrash_parser
from analysis import detect_regression_range
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.crash_report import CrashReport
from analysis.type_enums import CrashClient
from common import findit
from common import findit_for_chromecrash
from common.appengine_testcase import AppengineTestCase
from common.findit_for_clusterfuzz import FinditForClusterfuzz
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import analysis_status
from libs.deps import chrome_dependency_fetcher
from libs.gitiles.gitiles_repository import GitilesRepository



class FinditForClusterfuzzTest(AppengineTestCase):

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
