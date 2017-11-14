# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_failure_group import WfFailureGroup
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import try_job as try_job_service
from services.test_failure import test_try_job
from waterfall import swarming_util
from waterfall.test import wf_testcase


class TryJobUtilTest(wf_testcase.WaterfallTestCase):

  def testGetFailedStepsAndTests(self):
    failed_steps = {
        'step_c': {},
        'step_a': {
            'tests': {
                'test_c': {},
                'test_b': {},
                'test_a': {}
            },
        },
        'step_b': {}
    }

    expected_result = [['step_a', 'test_a'], ['step_a', 'test_b'],
                       ['step_a', 'test_c'], ['step_b', None], ['step_c', None]]

    self.assertEqual(expected_result,
                     test_try_job._GetStepsAndTests(failed_steps))

  def testFailedStepsAbsent(self):
    self.assertEqual([], test_try_job._GetStepsAndTests(None))

  def testNoFailedSteps(self):
    self.assertEqual([], test_try_job._GetStepsAndTests({}))

  def testDoNotGroupUnknownBuildFailure(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with UNKNOWN failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
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
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.INFRA, None,
            None, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testDoNotGroupTestWithNoSteps(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    blame_list = ['a']

    failed_steps = {}

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have zero failed steps.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testGroupTestsWithRelatedStepsWithHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    heuristic_result = {
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed steps.
    # Observe no new group creation.
    self.assertFalse(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testGroupTestsWithRelatedStepsWithoutHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed steps.
    # Observe no new group creation.
    self.assertFalse(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDisjointBlameLists(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list_1 = ['a']
    blame_list_2 = ['b']
    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list_1, failed_steps, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list_2, failed_steps, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDifferentHeuristicResults(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']
    failed_steps = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

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
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result_1))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps, heuristic_result_2))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupTestsWithDifferentSteps(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'

    blame_list = ['a']

    failed_steps_1 = {
        'step_a': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    failed_steps_2 = {
        'step_b': {
            'current_failure': 3,
            'first_failure': 2,
            'last_pass': 1
        }
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps_1, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed steps.
    # Observe new group creation.
    self.assertTrue(
        test_try_job._IsTestFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.TEST,
            blame_list, failed_steps_2, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testBailOutForTestTryJob(self, mock_fn):
    master_name = 'master2'
    builder_name = 'builder2'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'a_test': {}
        },
        'failure_type': failure_type.TEST
    }

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(master_name, builder_name,
                                           build_number).key
    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewTestTryJobIfNotFirstTimeFailure(self, mock_fn):
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
        'failure_type': failure_type.TEST
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    mock_fn.return_value = False
    expected_key = WfTryJob.Create(master_name, builder_name, build_number).key
    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_key, try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewTestTryJobIfNoNewFailure(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        },
        'failure_type': failure_type.TEST
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a': {'a.t2': 'm/b/222'}}
    analysis.put()

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(master_name, builder_name,
                                           build_number).key

    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewTestTryJobIfTestFailureSwarming(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'a.PRE_t1': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 221,
                        'base_test_name': 'a.t1'
                    },
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'a.t3': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 222
                    }
                }
            },
            'b': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'b.t1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'b.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
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
        'failure_type': failure_type.TEST
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a': {
            'a.PRE_t1': 'm/b/223',
            'a.t2': 'm/b/222',
            'a.t3': 'm/b/223'
        },
        'b': {
            'b.t1': 'm/b/222',
            'b.t2': 'm/b/222'
        }
    }
    analysis.put()

    mock_fn.return_value = False

    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewTestTryJobForOtherType(self, mock_fn):
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

    need_try_job, _ = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=False)
  def testNotNeedANewTestTryJob(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, None, None, None)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewTryJobIfNoNewFailure(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            '': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        },
        'failure_type': failure_type.TEST
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a': {'a.t2': 'm/b/222'}}
    analysis.put()

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(master_name, builder_name,
                                           build_number).key

    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewTryJobIfTestFailureSwarming(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'a.PRE_t1': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 221,
                        'base_test_name': 'a.t1'
                    },
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'a.t3': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 222
                    }
                }
            },
            'b': {
                'current_failure': 223,
                'first_failure': 222,
                'last_pass': 221,
                'tests': {
                    'b.t1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'b.t2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
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
        'failure_type': failure_type.TEST
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'a': {
            'a.PRE_t1': 'm/b/223',
            'a.t2': 'm/b/222',
            'a.t3': 'm/b/223'
        },
        'b': {
            'b.t1': 'm/b/222',
            'b.t2': 'm/b/222'
        }
    }
    analysis.put()

    mock_fn.return_value = False

    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, None)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  def testForceTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222,
                'tests': {
                    'a.t2': {
                        'current_failure': 223,
                        'first_failure': 223,
                        'last_pass': 222
                    }
                }
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
        'failure_type': failure_type.TEST
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [['rev', 'failed']]
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a': {'a.t2': 'm/b/223'}}
    analysis.put()

    need_try_job, try_job_key = test_try_job.NeedANewTestTryJob(
        master_name, builder_name, build_number, failure_info, None, True)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job_key, try_job.key)

  def testGetLastPassTestNoLastPass(self):
    failed_steps = {
        'a': {
            'first_failure': 1,
            'last_pass': 0,
            'tests': {
                'test1': {
                    'first_failure': 1
                }
            }
        }
    }
    self.assertIsNone(test_try_job._GetLastPassTest(1, failed_steps))

  def testGetLastPassTest(self):
    failed_steps = {
        'a': {
            'first_failure': 1,
            'last_pass': 0,
            'tests': {
                'test1': {
                    'first_failure': 1,
                    'last_pass': 0
                }
            }
        }
    }
    self.assertEqual(0, test_try_job._GetLastPassTest(1, failed_steps))

  def testGetGoodRevisionTest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = {
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    }
                }
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
                     test_try_job._GetGoodRevisionTest(
                         master_name, builder_name, build_number, failure_info))

  def testNotGetGoodRevisionTtest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    }
                }
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
        test_try_job._GetGoodRevisionTest(master_name, builder_name,
                                          build_number, failure_info))

  @mock.patch.object(test_try_job, 'GetReliableTests', return_value={})
  @mock.patch.object(swarming_util, 'GetCacheName', return_value='cache')
  def testGetParametersToScheduleTestTryJob(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = {
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    }
                }
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
        'task_results': {},
        'dimensions': ['os:Mac-10.9', 'cpu:x86-64', 'pool:Chrome.Findit'],
        'cache_name': 'cache'
    }
    self.assertEqual(expected_parameters,
                     test_try_job.GetParametersToScheduleTestTryJob(
                         master_name, builder_name, build_number, failure_info,
                         None))

  def testGetSwarmingTasksResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.TEST
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'a on platform': {
                'first_failure': 1,
                'tests': {
                    'test1': {
                        'first_failure': 1
                    },
                    'test2': {
                        'first_failure': 1
                    }
                }
            },
            'b': {
                'first_failure': 1,
                'tests': {
                    'b_test1': {
                        'first_failure': 1
                    }
                }
            },
            'c': {
                'first_failure': 0,
                'tests': {
                    'b_test1': {
                        'first_failure': 0
                    }
                }
            }
        }
    }

    task1 = WfSwarmingTask.Create(master_name, builder_name, build_number,
                                  'a on platform')
    task1.tests_statuses = {'test1': {'SUCCESS': 6}, 'test2': {'FAILURE': 6}}
    task1.canonical_step_name = 'a'
    task1.put()

    task2 = WfSwarmingTask.Create(master_name, builder_name, build_number, 'b')
    task2.tests_statuses = {'b_test1': {'SUCCESS': 6}}
    task2.put()

    task_results = test_try_job.GetReliableTests(master_name, builder_name,
                                                 build_number, failure_info)

    expected_results = {'a': ['test2']}

    self.assertEqual(expected_results, task_results)

  def testGetReliableTestsNoTask(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.TEST
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'a on platform': {
                'first_failure': 1,
                'tests': {
                    'test1': {
                        'first_failure': 1
                    },
                    'test2': {
                        'first_failure': 1
                    }
                }
            },
            'b': {
                'first_failure': 1,
                'tests': {
                    'b_test1': {
                        'first_failure': 1
                    }
                }
            },
            'c': {
                'first_failure': 0,
                'tests': {
                    'b_test1': {
                        'first_failure': 0
                    }
                }
            }
        }
    }
    self.assertEqual({},
                     test_try_job.GetReliableTests(master_name, builder_name,
                                                   build_number, failure_info))

  def testGetBuildPropertiesForTestFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    expected_properties = {
        'recipe':
            'findit/chromium/test',
        'good_revision':
            1,
        'bad_revision':
            2,
        'target_mastername':
            master_name,
        'target_testername':
            'b',
        'suspected_revisions': [],
        'referenced_build_url': ('https://ci.chromium.org/buildbot/%s/%s/%s') %
                                (master_name, builder_name, build_number)
    }
    properties = test_try_job.GetBuildProperties(master_name, builder_name,
                                                 build_number, 1, 2, None)

    self.assertEqual(properties, expected_properties)
