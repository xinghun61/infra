# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model import wf_analysis_status
from model.wf_try_job import WfTryJob


class WfTryJobTest(unittest.TestCase):
  def testWfTryJobStatusIsCompleted(self):
    for status in (wf_analysis_status.ANALYZED, wf_analysis_status.ERROR):
      tryjob = WfTryJob.Create('m', 'b', 123)
      tryjob.status = status
      self.assertTrue(tryjob.completed)

  def testWfTryJobStatusIsNotCompleted(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING):
      tryjob = WfTryJob.Create('m', 'b', 123)
      tryjob.status = status
      self.assertFalse(tryjob.completed)

  def testWfTryJobStatusIsFailed(self):
    tryjob = WfTryJob.Create('m', 'b', 123)
    tryjob.status = wf_analysis_status.ERROR
    self.assertTrue(tryjob.failed)

  def testWfTryJobStatusIsNotFailed(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING,
                   wf_analysis_status.ANALYZED):
      tryjob = WfTryJob.Create('m', 'b', 123)
      tryjob.status = status
      self.assertFalse(tryjob.failed)
