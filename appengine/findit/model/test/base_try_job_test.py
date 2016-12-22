# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model import analysis_status
from model.wf_try_job import WfTryJob


class BaseTryJobTest(unittest.TestCase):

  def testTryJobStatusIsCompleted(self):
    for status in (analysis_status.COMPLETED, analysis_status.ERROR):
      try_job = WfTryJob.Create('m', 'b', 123)
      try_job.status = status
      self.assertTrue(try_job.completed)

  def testTryJobStatusIsNotCompleted(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING):
      try_job = WfTryJob.Create('m', 'b', 123)
      try_job.status = status
      self.assertFalse(try_job.completed)

  def testTryJobStatusIsFailed(self):
    try_job = WfTryJob.Create('m', 'b', 123)
    try_job.status = analysis_status.ERROR
    self.assertTrue(try_job.failed)

  def testTryJobStatusIsNotFailed(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED):
      try_job = WfTryJob.Create('m', 'b', 123)
      try_job.status = status
      self.assertFalse(try_job.failed)
