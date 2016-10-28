# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from common import time_util
from common.waterfall import failure_type
from model import analysis_approach_type
from model import suspected_cl_status
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import build_util
from waterfall import suspected_cl_util
from waterfall.test import wf_testcase


class SuspectedCLUtilTest(wf_testcase.WaterfallTestCase):

  def testCreateWfSuspectedCL(self):
    approach = analysis_approach_type.HEURISTIC
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    compile_failure_type = failure_type.COMPILE
    repo_name = 'chromium'
    revision = 'r1'
    commit_position = 1
    failures = {'compile': []}
    top_score = 5

    mocked_utcnow = datetime.datetime(2016, 10, 4, 0, 0, 0)
    self.MockUTCNow(mocked_utcnow)

    self.assertIsNone(WfSuspectedCL.Get(repo_name, revision))

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, compile_failure_type, failures, top_score)

    expected_builds = {
        build_util.CreateBuildId(master_name, builder_name, build_number ):{
              'approaches': [approach],
              'failure_type': compile_failure_type,
              'failures': failures,
              'status': None,
              'top_score': top_score
        }
    }

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual(
        [analysis_approach_type.HEURISTIC], suspected_cl.approaches)
    self.assertEqual([compile_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)
    self.assertEqual(mocked_utcnow, suspected_cl.identified_time)
    self.assertEqual(mocked_utcnow, suspected_cl.updated_time)

  def testUpdateWfSuspectedCLAddAnotherApproach(self):
    approach = analysis_approach_type.TRY_JOB
    master_name = 'm'
    builder_name = 'b'
    build_number = 122
    test_failure_type = failure_type.TEST
    repo_name = 'chromium'
    revision = 'r2'
    commit_position = 2
    failures = {'step_1': ['test1', 'test2']}
    top_score = None

    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        build_util.CreateBuildId(
            master_name, builder_name, build_number ): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }
    suspected_cl.failure_type = [test_failure_type]
    suspected_cl.put()

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, test_failure_type, failures, top_score)

    expected_builds = {
        build_util.CreateBuildId(
            master_name, builder_name, build_number ): {
            'approaches': [
                analysis_approach_type.HEURISTIC,
                analysis_approach_type.TRY_JOB],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }

    expected_approaches = [
        analysis_approach_type.HEURISTIC,
        analysis_approach_type.TRY_JOB]

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual(expected_approaches, suspected_cl.approaches)
    self.assertEqual([test_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testUpdateWfSuspectedCLAddSameBuild(self):
    approach = analysis_approach_type.HEURISTIC
    master_name = 'm'
    builder_name = 'b'
    build_number = 122
    test_failure_type = failure_type.TEST
    repo_name = 'chromium'
    revision = 'r2'
    commit_position = 2
    failures = {'step_1': ['test1', 'test2']}
    top_score = 4

    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        build_util.CreateBuildId(
            master_name, builder_name, build_number ): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }
    suspected_cl.failure_type = [test_failure_type]
    suspected_cl.put()

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, test_failure_type, failures, top_score)

    expected_builds = {
        build_util.CreateBuildId(
            master_name, builder_name, build_number ): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }

    expected_approaches = [analysis_approach_type.HEURISTIC]

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual(expected_approaches, suspected_cl.approaches)
    self.assertEqual([test_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testUpdateWfSuspectedCLAddAnotherHeuristic(self):
    approach = analysis_approach_type.HEURISTIC
    master_name = 'm'
    builder_name = 'b'
    build_number = 122
    test_failure_type = failure_type.TEST
    repo_name = 'chromium'
    revision = 'r2'
    commit_position = 2
    failures = {'step_1': ['test1', 'test2']}
    top_score = 4

    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        build_util.CreateBuildId(
            master_name, builder_name, build_number-1): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': {'step': ['test']},
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        },
        build_util.CreateBuildId(
            master_name, builder_name, build_number - 2): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        }
    }
    suspected_cl.failure_type = [test_failure_type]
    suspected_cl.put()

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, test_failure_type, failures, top_score)

    expected_builds = {
        build_util.CreateBuildId(
            master_name, builder_name, build_number-1): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': {'step': ['test']},
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        },
        build_util.CreateBuildId(
            master_name, builder_name, build_number - 2): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        },
        build_util.CreateBuildId(
            master_name, builder_name, build_number): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        }
    }

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual(
        [analysis_approach_type.HEURISTIC], suspected_cl.approaches)
    self.assertEqual([test_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testGetCLInfo(self):
    self.assertEqual(['chromium', 'rev1'],
                     suspected_cl_util.GetCLInfo('chromium/rev1'))
