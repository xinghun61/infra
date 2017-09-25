# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from libs import analysis_status
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from services import try_job as try_job_util
from services.compile_failure import compile_failure_analysis
from services.compile_failure import compile_try_job
from waterfall import suspected_cl_util
from waterfall import swarming_util
from waterfall.test import wf_testcase


class TryJobUtilTest(wf_testcase.WaterfallTestCase):

  def testDoNotGroupUnknownBuildFailure(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with UNKNOWN failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.UNKNOWN, None,
            None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testDoNotGroupInfraBuildFailure(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with INFRA failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.INFRA, None,
            None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testDoNotGroupCompileWithNoOutputNodes(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    blame_list = ['a']

    signals = {'compile': {'failed_output_nodes': []}}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have zero failed output nodes.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    blame_list = ['a']

    signals = {'compile': {'failed_output_nodes': ['abc.obj']}}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual([master_name, builder_name, build_number],
                     analysis.failure_group_key)

  def testSecondAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {'compile': {'failed_output_nodes': ['abc.obj']}}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))

    analysis_2 = WfAnalysis.Get(master_name_2, builder_name, build_number)
    self.assertEqual([master_name, builder_name, build_number],
                     analysis_2.failure_group_key)

  def testGroupCompilesWithRelatedFailuresWithHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {'compile': {'failed_output_nodes': ['abc.obj']}}

    heuristic_result = {
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testGroupCompilesWithRelatedFailuresWithoutHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {'compile': {'failed_output_nodes': ['abc.obj']}}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDisjointBlameLists(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list_1 = ['a']

    blame_list_2 = ['b']

    signals = {'compile': {'failed_output_nodes': ['abc.obj']}}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list_1, signals, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list_2, signals, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDifferentHeuristicResults(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = {'compile': {'failed_output_nodes': ['abc.obj']}}

    heuristic_result_1 = {
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    }

    heuristic_result_2 = {
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev2',
            }],
        }]
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result_1))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result_2))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDifferentOutputNodes(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    signals_1 = {'compile': {'failed_output_nodes': ['abc.obj']}}

    signals_2 = {'compile': {'failed_output_nodes': ['def.obj']}}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals_1, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals_2, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobIfNotFirstTimeFailure(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 221,
                'last_pass': 220
            }
        },
        'builds': {
            '220': {
                'blame_list': ['220-1', '220-2'],
                'chromium_revision': '220-2'
            },
            '221': {
                'blame_list': ['221-1', '221-2'],
                'chromium_revision': '221-2'
            },
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    mock_fn.return_value = False
    expected_key = WfTryJob.Create(master_name, builder_name, build_number).key
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobIfOneWithResultExists(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [['rev', 'failed']]
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(try_job_key, try_job.key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewCompileTryJobIfExistingOneHasError(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job.key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewTryJobIfExistingOneHasError(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job.key, try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewTestTryJob(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'compile': 'm/b/223'}
    analysis.put()

    mock_fn.return_value = False

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewCompileTryJob(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'compile': 'm/b/223'}
    analysis.put()

    mock_fn.return_value = False

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(
      try_job_util, 'NeedANewWaterfallTryJob', return_value=False)
  def testNotNeedANewCompileTryJob(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, None, None, None)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobForOtherType(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.UNKNOWN
    }

    mock_fn.return_value = False

    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_util, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobForCompileTypeNoFailureInfo(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(master_name, builder_name,
                                           build_number).key
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  def testUseFailedOutputNodesFromSignals(self):
    signals = {
        'compile': {
            'failed_targets': [
                {
                    'target': 'a.exe'
                },
                {
                    'source': 'b.cc',
                    'target': 'b.o'
                },
            ],
            'failed_output_nodes': ['a', 'b'],
        }
    }

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(signals, 'm', 'b'),
        ['a', 'b'])

  def testGetFailedTargetsFromSignals(self):
    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals({}, 'm', 'b'), [])

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals({
            'compile': {}
        }, 'm', 'b'), [])

    signals = {
        'compile': {
            'failed_targets': [{
                'target': 'a.exe'
            }, {
                'source': 'b.cc',
                'target': 'b.o'
            }]
        }
    }

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(signals, 'm', 'b'),
        ['a.exe'])

  def testUseObjectFilesAsFailedTargetIfStrictRegexUsed(self):
    signals = {
        'compile': {
            'failed_targets': [
                {
                    'source': 'b.cc',
                    'target': 'b.o'
                },
            ]
        }
    }

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(signals, 'master1',
                                                     'builder1'), ['b.o'])

  def testGetLastPassCurrentBuildIsNotFirstFailure(self):
    failed_steps = {'compile': {'first_failure': 1, 'last_pass': 0}}
    self.assertIsNone(compile_try_job._GetLastPassCompile(2, failed_steps))

  def testGetLastPassCompile(self):
    failed_steps = {'compile': {'first_failure': 1, 'last_pass': 0}}
    self.assertEqual(0, compile_try_job._GetLastPassCompile(1, failed_steps))

  def testGetGoodRevisionCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = {
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    }
    self.assertEqual('rev1',
                     compile_try_job._GetGoodRevisionCompile(
                         master_name, builder_name, build_number, failure_info))

  def testNotGetGoodRevisionCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    }
    self.assertIsNone(
        compile_try_job._GetGoodRevisionCompile(master_name, builder_name,
                                                build_number, failure_info))

  @mock.patch.object(swarming_util, 'GetCacheName', return_value='cache')
  def testGetParametersToScheduleTestTryJob(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = {
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0,
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    }

    expected_parameters = {
        'bad_revision': 'rev2',
        'suspected_revisions': [],
        'good_revision': 'rev1',
        'compile_targets': [],
        'dimensions': ['os:Mac-10.9', 'cpu:x86-64', 'pool:Chrome.Findit'],
        'cache_name': 'cache'
    }
    self.assertEqual(expected_parameters,
                     compile_try_job.GetParametersToScheduleCompileTryJob(
                         master_name, builder_name, build_number, failure_info,
                         None, None))

  def testGetFailedRevisionFromCompileResult(self):
    culprit = '1234567'
    compile_result = {'report': {'culprit': culprit}}
    self.assertEqual(
        culprit,
        compile_try_job.GetFailedRevisionFromCompileResult(compile_result))

  def testCompileFailureIsNotFlaky(self):
    result = {
        'report': {
            'culprit': 'rev',
            'result': 'result',
            'metadata': {
                'sub_ranges': []
            }
        }
    }
    self.assertFalse(compile_try_job.CompileFailureIsFlaky(result))

  def testCompileFailureIsFlakyNoResult(self):
    self.assertFalse(compile_try_job.CompileFailureIsFlaky(None))

  def testCompileFailureIsFlaky(self):
    result = {
        'report': {
            'result': {
                'r0': 'failed',
                'r1': 'passed',
                'r2': 'passed',
                'r3': 'passed',
                'r4': 'passed',
            },
            'metadata': {
                'sub_ranges': [[None, 'r1', 'r2'], ['r3', 'r4']]
            }
        }
    }
    self.assertTrue(compile_try_job.CompileFailureIsFlaky(result))

  def testUpdateTryJobResultNoCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    WfTryJob.Create(master_name, builder_name, build_number).put()
    compile_try_job.UpdateTryJobResult(master_name, builder_name, build_number,
                                       None, None, None)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

  def testUpdateTryJobResultUpdat(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    result = {'culprit': {'compile': 'rev'}}
    culprits = {'rev': {'revision': 'rev'}}
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [{'try_job_id': '2'}]
    try_job.put()

    expected_results = [{'try_job_id': '2', 'culprit': {'compile': 'rev'}}]

    compile_try_job.UpdateTryJobResult(master_name, builder_name, build_number,
                                       result, '2', culprits)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertEqual(expected_results, try_job.compile_results)

  def testUpdateTryJobResultAppend(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    result = {'culprit': {'compile': 'rev'}}
    culprits = {'rev': {'revision': 'rev'}}
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [{'try_job_id': '1'}]
    try_job.put()

    expected_results = [{'try_job_id': '1'}, {'culprit': {'compile': 'rev'}}]

    compile_try_job.UpdateTryJobResult(master_name, builder_name, build_number,
                                       result, '2', culprits)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertListEqual(expected_results, try_job.compile_results)

  @mock.patch.object(compile_try_job, '_GetUpdatedAnalysisResult')
  def testUpdateWfAnalysisWithTryJobResultNoCulprit(self, mock_fn):
    compile_try_job.UpdateWfAnalysisWithTryJobResult('m', 'b', 1, None, None,
                                                     False)
    mock_fn.assert_not_called()

  @mock.patch.object(
      try_job_util,
      'GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  @mock.patch.object(
      compile_failure_analysis, 'GetUpdatedSuspectedCLs', return_value=[])
  def testUpdateWfAnalysisWithTryJobResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'compile',
        }]
    }
    analysis.put()
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}

    compile_try_job.UpdateWfAnalysisWithTryJobResult(
        master_name, builder_name, build_number, None, culprits, False)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(result_status.FOUND_UNTRIAGED, analysis.result_status)

  @mock.patch.object(try_job_util, 'GetResultAnalysisStatus', return_value=None)
  @mock.patch.object(
      compile_failure_analysis, 'GetUpdatedSuspectedCLs', return_value=None)
  def testNoNeedToUpdateWfAnalysisWithTryJobResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}

    compile_try_job.UpdateWfAnalysisWithTryJobResult(
        master_name, builder_name, build_number, None, culprits, False)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNone(analysis.result_status)

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLsNoCulprit(self, mock_fn):
    compile_try_job.UpdateSuspectedCLs('m', 'b', 1, None)
    mock_fn.assert_not_called()

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLs(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}
    compile_try_job.UpdateSuspectedCLs(master_name, builder_name, build_number,
                                       culprits)
    mock_fn.assert_called_with(
        'chromium', 'rev', None, analysis_approach_type.TRY_JOB, master_name,
        builder_name, build_number, failure_type.COMPILE, {'compile': []}, None)

  def testGetUpdatedAnalysisResultFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'Failure_reason'
        }, {
            'step_name': 'compile',
        }]
    }
    analysis.put()

    expected_result = {
        'failures': [{
            'step_name': 'Failure_reason'
        }, {
            'step_name': 'compile',
            'flaky': True
        }]
    }
    self.assertEqual(expected_result,
                     compile_try_job._GetUpdatedAnalysisResult(analysis, True))
