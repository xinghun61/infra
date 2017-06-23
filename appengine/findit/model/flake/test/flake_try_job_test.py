# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.flake.flake_try_job import FlakeTryJob


class FlakeTryJobTest(TestCase):

  def testCreate(self):
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3')
    self.assertEqual([], try_job.try_job_ids)
    self.assertEqual([], try_job.flake_results)

  def testGet(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3'
    try_job_id = 'try_job_id'

    try_job_before = FlakeTryJob.Create(master_name, builder_name, step_name,
                                        test_name, git_hash)
    try_job_before.try_job_ids = [try_job_id]
    try_job_before.put()

    try_job_after = FlakeTryJob.Get(master_name, builder_name, step_name,
                                    test_name, git_hash)
    self.assertEqual([try_job_id], try_job_after.try_job_ids)

  def testProperties(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3'

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, git_hash)
    self.assertEqual(master_name, try_job.master_name)
    self.assertEqual(builder_name, try_job.builder_name)
    self.assertEqual(step_name, try_job.step_name)
    self.assertEqual(test_name, try_job.test_name)
    self.assertEqual(git_hash, try_job.git_hash)
