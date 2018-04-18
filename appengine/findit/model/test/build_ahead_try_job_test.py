# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.build_ahead_try_job import BuildAheadTryJob


class BuildAheadTryJobTest(TestCase):

  def testCreate(self):
    build_id = '8953484774825114240'
    platform = 'mac'
    cache_name = 'build_1231234'
    try_job = BuildAheadTryJob.Create(build_id, platform, cache_name)
    self.assertEqual(platform, try_job.platform)
    self.assertEqual(True, try_job.running)
    self.assertEqual(cache_name, try_job.cache_name)

  def testGet(self):
    build_id = '8953484774825114288'
    platform = 'win'
    cache_name = 'build_abcabcd'

    dummy_metadata = {"dummy": "metadata"}

    try_job_before = BuildAheadTryJob.Create(build_id, platform, cache_name)
    try_job_before.MarkComplete(dummy_metadata)

    try_job_after = BuildAheadTryJob.Get(build_id)
    self.assertEqual(dummy_metadata, try_job_after.last_buildbucket_response)
    self.assertEqual(build_id, try_job_after.BuildId)
    self.assertFalse(try_job_after.running)

  def testRunningJobs(self):
    build_id = '8953484774825114288'
    platform = 'win'
    cache_name = 'build_abcabcd'

    BuildAheadTryJob.Create(build_id, platform, cache_name).put()

    build_id = '8953484774825114289'
    platform = 'mac'
    cache_name = 'build_1231234'

    BuildAheadTryJob.Create(build_id, platform, cache_name).put()

    build_id = '8953484774825114290'
    platform = 'unix'
    cache_name = 'build_1010100'

    BuildAheadTryJob.Create(build_id, platform, cache_name).put()

    self.assertEqual(3, len(BuildAheadTryJob.RunningJobs()))
    self.assertEqual(1, len(BuildAheadTryJob.RunningJobs(platform='win')))
