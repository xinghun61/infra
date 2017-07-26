# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.type_enums import CrashClient
from frontend.handlers.uma_sampling_profiler_result_feedback import (
    UMASamplingProfilerResultFeedback)
from testing_utils import testing
import unittest


class UMASamplingProfilerResultFeedbackTest(unittest.TestCase):

  def testClient(self):
    """Tests that the client is CrashClient.UMA_SAMPLING_PROFILER."""
    result_feedback = UMASamplingProfilerResultFeedback()
    self.assertEqual(result_feedback.client, CrashClient.UMA_SAMPLING_PROFILER)

