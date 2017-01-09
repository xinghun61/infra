# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData


class WfTryJobDataTest(TestCase):

  def testProperties(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    try_job_id = 'try_job_id'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key

    self.assertEqual(master_name, try_job_data.master_name)
    self.assertEqual(builder_name, try_job_data.builder_name)
    self.assertEqual(build_number, try_job_data.build_number)
