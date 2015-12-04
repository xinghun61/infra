# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from testing_utils import testing

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall import try_job_util


class _MockRootPipeline(object):
  STARTED = False

  def __init__(self, *_):
    pass

  def start(self, _):
    _MockRootPipeline.STARTED = True


class TryJobUtilTest(testing.AppengineTestCase):
  def testNotNeedANewTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    revisions = ['rev1', 'rev2']
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 221,
            'last_pass': 220
        }
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    self.mock(
        try_job_util.try_job_pipeline, 'TryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    try_job_util.ScheduleTryJobIfNeeded(
        master_name, builder_name, build_number, failed_steps,
        revisions)

    self.assertFalse(_MockRootPipeline.STARTED)

  def testNotNeedANewTryJobIfNotCompileFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failed_steps = {
        'a': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 222
        }
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    new_try_job_needed, failure_result_map = try_job_util._NeedANewTryJob(
        master_name, builder_name, build_number, failed_steps)

    self.assertFalse(new_try_job_needed)
    self.assertEqual({}, failure_result_map)

  def testNotNeedANewTryJobIfOneWithResultExists(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 222
        }
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.result = [['rev', 'failed']]
    try_job.status = wf_analysis_status.ANALYZED
    try_job.put()

    new_try_job_needed, failure_result_map = try_job_util._NeedANewTryJob(
        master_name, builder_name, build_number, failed_steps)

    expected_failure_result_map = {
        'compile': 'm/b/223'
    }

    self.assertFalse(new_try_job_needed)
    self.assertEqual(expected_failure_result_map, failure_result_map)

  def testNeedANewTryJobIfExistingOneHasError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 222
        }
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = wf_analysis_status.ERROR
    try_job.put()

    new_try_job_needed, failure_result_map = try_job_util._NeedANewTryJob(
        master_name, builder_name, build_number, failed_steps)

    expected_failure_result_map = {
        'compile': 'm/b/223'
    }
    self.assertTrue(new_try_job_needed)
    self.assertEqual(expected_failure_result_map, failure_result_map)

  def testNeedANewTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    revisions = ['rev1', 'rev2']
    failed_steps = {
        'compile': {
            'current_failure': 223,
            'first_failure': 223,
            'last_pass': 222
        }
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    self.mock(
        try_job_util.try_job_pipeline, 'TryJobPipeline', _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    try_job_util.ScheduleTryJobIfNeeded(
        master_name, builder_name, build_number, failed_steps,
        revisions)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertTrue(_MockRootPipeline.STARTED)
    self.assertIsNotNone(try_job)
