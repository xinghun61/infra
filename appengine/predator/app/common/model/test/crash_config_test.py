# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from google.appengine.api import users

from analysis.type_enums import CrashClient
from common.appengine_testcase import AppengineTestCase
from common.model.crash_config import CrashConfig


DUMMY_COMPILED_COMPONENT_PATTERNS = {
    "path_function_component": [
        [
          re.compile("src/comp1.*"),
          None,
          "Comp1>Dummy"
        ],
        [
          re.compile("src/comp2.*"),
          re.compile("func2.*"),
          "Comp2>Dummy"
        ],
    ],
    "top_n": 4
}


DUMMY_COMPONENT_PATTERNS = {
    "path_function_component": [
        [
          "src/comp1.*",
          "",
          "Comp1>Dummy"
        ],
        [
          "src/comp2.*",
          "func2.*",
          "Comp2>Dummy"
        ],
    ],
    "top_n": 4
}

CONFIG_DATA = {
    'component_classifier': DUMMY_COMPONENT_PATTERNS,
}


class CrashConfigTest(AppengineTestCase):

  def setUp(self):
    super(CrashConfigTest, self).setUp()
    CrashConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **CONFIG_DATA)

  def testGetClientConfig(self):
    crash_config = CrashConfig.Get()
    self.assertIsNotNone(crash_config.GetClientConfig(CrashClient.FRACAS))
    self.assertIsNotNone(
        crash_config.GetClientConfig(CrashClient.UMA_SAMPLING_PROFILER))
    self.assertIsNone(crash_config.GetClientConfig('Unsupported_client'))
