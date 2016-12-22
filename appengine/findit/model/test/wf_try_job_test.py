# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.wf_try_job import WfTryJob


class WfTryJobTest(TestCase):

  def testCreate(self):
    try_job = WfTryJob.Create('m', 'b', 123)
    self.assertEqual([], try_job.try_job_ids)
    self.assertEqual([], try_job.compile_results)
    self.assertEqual([], try_job.test_results)

  def testGet(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    try_job_id = 'try_job_id'

    try_job_before = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_before.try_job_ids = [try_job_id]
    try_job_before.put()

    try_job_after = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual([try_job_id], try_job_after.try_job_ids)
