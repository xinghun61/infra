# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData


class FlakeTryJobDataTest(TestCase):

  def testProperties(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    try_job_id = 'try_job_id'

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, git_hash)
    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key

    self.assertEqual(master_name, try_job_data.master_name)
    self.assertEqual(builder_name, try_job_data.builder_name)
    self.assertEqual(step_name, try_job_data.step_name)
    self.assertEqual(test_name, try_job_data.test_name)
    self.assertEqual(git_hash, try_job_data.git_hash)
