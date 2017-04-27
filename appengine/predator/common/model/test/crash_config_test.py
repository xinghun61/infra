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


class CrashAnalysisTest(AppengineTestCase):

  def setUp(self):
    super(CrashAnalysisTest, self).setUp()
    CrashConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **CONFIG_DATA)

  def _VerifyTwoCompiledComponentClassifierEqual(self, setting1, setting2):
    self.assertEqual(setting1['top_n'], setting2['top_n'])
    self.assertEqual(len(setting1['path_function_component']),
                     len(setting2['path_function_component']))

    for i, (path1, function1, component1) in enumerate(
        setting1['path_function_component']):
      path2, function2, component2 = setting2['path_function_component'][i]
      self.assertEqual(path1.pattern, path2.pattern)
      if not function1:
        self.assertEqual(function1, function2)
      else:
        self.assertEqual(function1.pattern, function2.pattern)
      self.assertEqual(component1, component2)

  def testClearCache(self):
    crash_config = CrashConfig.Get()
    crash_config.ClearCache()

    self.assertIsNone(crash_config.cached_component_classifier)
    self._VerifyTwoCompiledComponentClassifierEqual(
        crash_config.compiled_component_classifier,
        DUMMY_COMPILED_COMPONENT_PATTERNS)

  def testGetCompiledComponentClassifierSettingFromCache(self):
    crash_config = CrashConfig.Get()
    crash_config.ClearCache()

    crash_config.cached_component_classifier = DUMMY_COMPILED_COMPONENT_PATTERNS
    self._VerifyTwoCompiledComponentClassifierEqual(
        crash_config.compiled_component_classifier,
        DUMMY_COMPILED_COMPONENT_PATTERNS)

  def testGetCompiledComponentClassifierSetting(self):
    crash_config = CrashConfig.Get()
    self.assertEqual(crash_config.component_classifier,
                     DUMMY_COMPONENT_PATTERNS)
    self._VerifyTwoCompiledComponentClassifierEqual(
        crash_config.compiled_component_classifier,
        DUMMY_COMPILED_COMPONENT_PATTERNS)

  def testGetClientConfig(self):
    crash_config = CrashConfig.Get()
    self.assertIsNotNone(crash_config.GetClientConfig(CrashClient.FRACAS))
    self.assertIsNone(crash_config.GetClientConfig('Unsupported_client'))
