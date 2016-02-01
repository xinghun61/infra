# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model import wf_analysis_status
from model.wf_try_job import WfTryJob


class WfTryJobTest(unittest.TestCase):
  def testWfTryJobStatusIsCompleted(self):
    for status in (wf_analysis_status.ANALYZED, wf_analysis_status.ERROR):
      try_job = WfTryJob.Create('m', 'b', 123)
      try_job.status = status
      self.assertTrue(try_job.completed)

  def testWfTryJobStatusIsNotCompleted(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING):
      try_job = WfTryJob.Create('m', 'b', 123)
      try_job.status = status
      self.assertFalse(try_job.completed)

  def testWfTryJobStatusIsFailed(self):
    try_job = WfTryJob.Create('m', 'b', 123)
    try_job.status = wf_analysis_status.ERROR
    self.assertTrue(try_job.failed)

  def testWfTryJobStatusIsNotFailed(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING,
                   wf_analysis_status.ANALYZED):
      try_job = WfTryJob.Create('m', 'b', 123)
      try_job.status = status
      self.assertFalse(try_job.failed)
