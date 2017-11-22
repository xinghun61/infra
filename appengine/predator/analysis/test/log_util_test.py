# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import log_util
from analysis.analysis_testcase import AnalysisTestCase


class LogUtilTest(AnalysisTestCase):

  def testLog(self):
    """Tests ``info``, ``warning`` and ``error`` functions."""
    log = self.GetMockLog()
    log_util.Log(log, 'info_name', 'info_msg', 'info',
                 stackdriver_logging=False)
    log_util.Log(log, 'error_name', 'error_msg', 'error')
    self.assertEqual(
        log.logs,
        [{'level': 'info', 'name': 'info_name', 'message': 'info_msg'},
         {'level': 'error', 'name': 'error_name', 'message': 'error_msg'}])

    log = None
    log_util.Log(log, 'error_name', 'error_msg', 'error')
    self.assertIsNone(log)

  def testLogInfo(self):
    """Tests ``info`` functions."""
    log = self.GetMockLog()
    log_util.LogInfo(log, 'info_name', 'info_msg')
    self.assertEqual(
        log.logs,
        [{'level': 'info', 'name': 'info_name', 'message': 'info_msg'}])

  def testLogWarning(self):
    """Tests ``warning`` functions."""
    log = self.GetMockLog()
    log_util.LogWarning(log, 'warning_name', 'warning_msg')
    self.assertEqual(
        log.logs,
        [{'level': 'warning', 'name': 'warning_name',
          'message': 'warning_msg'}])

  def testLogError(self):
    """Tests ``error`` functions."""
    log = self.GetMockLog()
    log_util.LogError(log, 'error_name', 'error_msg')
    self.assertEqual(
        log.logs,
        [{'level': 'error', 'name': 'error_name', 'message': 'error_msg'}])
