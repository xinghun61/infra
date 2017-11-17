# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import exceptions
from common.waterfall import failure_type
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_failure_group import WfFailureGroup
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import build_failure_analysis
from services import try_job as try_job_service
from services.parameters import BuildKey
from services.parameters import ScheduleTestTryJobParameters
from services.test_failure import test_try_job
from waterfall import suspected_cl_util
from waterfall import swarming_util
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class TryJobUtilTest(wf_testcase.WaterfallTestCase):

  def _MockGetChangeLog(self, revision):

    class MockedChangeLog(object):

      def __init__(self, commit_position, code_review_url):
        self.commit_position = commit_position
        self.code_review_url = code_review_url
        self.change_id = str(commit_position)

    mock_change_logs = {}
    mock_change_logs['rev1'] = MockedChangeLog(1, 'url_1')
    mock_change_logs['rev2'] = MockedChangeLog(2, 'url_2')
    return mock_change_logs.get(revision)

  def setUp(self):
    super(TryJobUtilTest, self).setUp()

    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

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

    expected_parameters = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        force_buildbot=False,
        dimensions=['os:Mac-10.9', 'cpu:x86-64', 'pool:Chrome.Findit'],
        cache_name='cache',
        targeted_tests={})
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

    pipeline_input = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='1',
        bad_revision='2',
        suspected_revisions=[],
        force_buildbot=False)

    expected_properties = {
        'recipe':
            'findit/chromium/test',
        'good_revision':
            '1',
        'bad_revision':
            '2',
        'target_mastername':
            master_name,
        'target_testername':
            'b',
        'suspected_revisions': [],
        'referenced_build_url': ('https://ci.chromium.org/buildbot/%s/%s/%s') %
                                (master_name, builder_name, build_number)
    }
    properties = test_try_job.GetBuildProperties(pipeline_input)

    self.assertEqual(properties, expected_properties)

  def testGetResultAnalysisStatusAllFlake(self):
    self.assertEqual(result_status.FLAKY,
                     test_try_job._GetResultAnalysisStatus(None, None, True))

  @mock.patch.object(
      try_job_service,
      'GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  def testGetResultAnalysisStatus(self, _):
    self.assertEqual(result_status.FOUND_UNTRIAGED,
                     test_try_job._GetResultAnalysisStatus(None, None))

  def testGetTestFailureCausedByCL(self):
    self.assertIsNone(test_try_job._GetTestFailureCausedByCL(None))

  def testGetTestFailureCausedByCLPassed(self):
    result = {
        'a_test': {
            'status': 'passed',
            'valid': True,
        },
        'b_test': {
            'status': 'failed',
            'valid': True,
            'failures': ['b_test1']
        }
    }

    expected_failures = {'b_test': ['b_test1']}

    self.assertEqual(expected_failures,
                     test_try_job._GetTestFailureCausedByCL(result))

  def testGetSuspectedCLsForTestTryJobAndHeuristicResultsSame(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    try_job_suspected_cls = {'rev1': suspected_cl}

    updated_cls = test_try_job._GetUpdatedSuspectedCLs(analysis, None,
                                                       try_job_suspected_cls)

    self.assertEqual(updated_cls, [suspected_cl])

  def testGetSuspectedCLsForTestTryJob(self):
    suspected_cl1 = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    suspected_cl2 = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }
    suspected_cl3 = {
        'revision': 'rev3',
        'commit_position': 3,
        'url': 'url_3',
        'repo_name': 'chromium'
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl3]
    analysis.put()

    try_job_suspected_cls = {'rev1': suspected_cl1, 'rev2': suspected_cl2}

    result = {
        'report': {
            'result': {
                'rev1': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1']
                    }
                },
                'rev2': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test2']
                    }
                }
            }
        }
    }

    expected_cls = [
        suspected_cl3, {
            'revision': 'rev1',
            'commit_position': 1,
            'url': 'url_1',
            'repo_name': 'chromium',
            'failures': {
                'step1': ['test1']
            },
            'top_score': None
        }, {
            'revision': 'rev2',
            'commit_position': 2,
            'url': 'url_2',
            'repo_name': 'chromium',
            'failures': {
                'step1': ['test2']
            },
            'top_score': None
        }
    ]

    cl_result = test_try_job._GetUpdatedSuspectedCLs(analysis, result,
                                                     try_job_suspected_cls)
    self.assertEqual(cl_result, expected_cls)

  def testGetSuspectedCLsForTestTryJobWithHeuristicResult(self):
    suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium',
        'failures': {
            'step1': ['test1']
        },
        'top_score': 2
    }

    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [suspected_cl]
    analysis.put()

    result = {
        'report': {
            'result': {
                'rev1': {
                    'step1': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1']
                    }
                }
            }
        }
    }

    self.assertEqual(
        test_try_job._GetUpdatedSuspectedCLs(analysis, result, {}),
        [suspected_cl])

  def testFindCulpritForEachTestFailureRevisionNotRun(self):
    result = {'report': {'result': {'rev2': 'passed'}}}

    culprit_map, failed_revisions = test_try_job.FindCulpritForEachTestFailure(
        result)
    self.assertEqual(culprit_map, {})
    self.assertEqual(failed_revisions, [])

  def testFindCulpritForEachTestFailureCulpritsReturned(self):
    result = {'report': {'culprits': {'a_tests': {'Test1': 'rev1'}}}}

    culprit_map, failed_revisions = test_try_job.FindCulpritForEachTestFailure(
        result)

    expected_culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1'
                }
            }
        }
    }

    self.assertEqual(culprit_map, expected_culprit_map)
    self.assertEqual(failed_revisions, ['rev1'])

  def testUpdateTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    WfTryJob.Create(master_name, builder_name, build_number).put()
    test_try_job.UpdateTryJobResult(master_name, builder_name, build_number,
                                    None, '123', None)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job.status, analysis_status.COMPLETED)

  def testGetUpdatedAnalysisResultNoAnalysis(self):
    self.assertEqual(([], False),
                     test_try_job._GetUpdatedAnalysisResult(None, {}))

  @mock.patch.object(swarming_util, 'UpdateAnalysisResult', return_value=True)
  def testGetUpdatedAnalysisResult(self, _):
    result = {'failures': [{'step_name': 'step1'}]}

    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.result = result
    analysis.put()

    self.assertEqual((result, True),
                     test_try_job._GetUpdatedAnalysisResult(analysis, {}))

  def testUpdateCulpritMapWithCulpritInfo(self):
    culprit_map = {'a_tests': {'tests': {'Test1': {'revision': 'rev1'}}}}
    culprits = {'rev1': {'revision': 'rev1', 'repo_name': 'chromium'}}

    expected_culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1',
                    'repo_name': 'chromium'
                }
            }
        }
    }

    test_try_job.UpdateCulpritMapWithCulpritInfo(culprit_map, culprits)
    self.assertEqual(expected_culprit_map, culprit_map)

  def testGetCulpritDataForTest(self):
    culprit_map = {
        'a_tests': {
            'tests': {
                'Test1': {
                    'revision': 'rev1',
                    'repo_name': 'chromium'
                }
            }
        }
    }

    expected_culprit_data = {'a_tests': {'Test1': 'rev1'}}

    self.assertEqual(expected_culprit_data,
                     test_try_job.GetCulpritDataForTest(culprit_map))

  @mock.patch.object(test_try_job, '_GetUpdatedAnalysisResult')
  def testUpdateWfAnalysisWithTryJobResultNoUpdate(self, mock_fn):
    test_try_job.UpdateWfAnalysisWithTryJobResult('m', 'n', 1, None, None, None)
    mock_fn.assert_not_called()

  @mock.patch.object(
      test_try_job, '_GetUpdatedAnalysisResult', return_value=({}, True))
  @mock.patch.object(
      test_try_job,
      '_GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  @mock.patch.object(test_try_job, '_GetUpdatedSuspectedCLs', return_value=[])
  def testUpdateWfAnalysisWithTryJobResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    test_try_job.UpdateWfAnalysisWithTryJobResult(
        master_name, builder_name, build_number, {}, ['rev1'], {})
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLsNoCulprit(self, mock_fn):
    test_try_job.UpdateSuspectedCLs('m', 'b', 1, None, None)
    mock_fn.assert_not_called()

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLs(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    result = {
        'report': {
            'result': {
                'rev': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            }
        }
    }
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}
    test_try_job.UpdateSuspectedCLs(master_name, builder_name, build_number,
                                    culprits, result)
    mock_fn.assert_called_with('chromium', 'rev', None,
                               analysis_approach_type.TRY_JOB, master_name,
                               builder_name, build_number, failure_type.TEST,
                               {'b_test': ['b_test1']}, None)

  def _CreateEntities(self, master_name, builder_name, build_number, try_job_id,
                      try_job_status, test_results):
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = try_job_status
    try_job.test_results = test_results
    try_job.put()

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

  def testIdentifyCulpritForTestTryJobSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    a_test1_suspected_cl = {
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium'
    }
    a_test2_suspected_cl = {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium'
    }

    expected_test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id,
        'culprit': {
            'a_test': {
                'tests': {
                    'a_test1': a_test1_suspected_cl,
                    'a_test2': a_test2_suspected_cl
                }
            }
        }
    }

    culprits, _ = test_try_job.IdentifyTestTryJobCulprits(
        master_name, builder_name, build_number, try_job_id, test_result)

    expected_culprits = {
        'rev1': {
            'revision': 'rev1',
            'repo_name': 'chromium',
            'commit_position': 1,
            'url': 'url_1'
        },
        'rev2': {
            'revision': 'rev2',
            'repo_name': 'chromium',
            'commit_position': 2,
            'url': 'url_2'
        }
    }
    self.assertEqual(culprits, expected_culprits)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    expected_culprit_data = {
        'a_test': {
            'a_test1': 'rev1',
            'a_test2': 'rev2',
        }
    }

    expected_cls = [{
        'revision': 'rev1',
        'commit_position': 1,
        'url': 'url_1',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1'],
            'b_test': ['b_test1'],
        },
        'top_score': None
    }, {
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium',
        'failures': {
            'a_test': ['a_test1', 'a_test2'],
            'b_test': ['b_test1'],
        },
        'top_score': None
    }]
    self.assertEqual(expected_culprit_data, try_job_data.culprits)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_cls)

  @mock.patch.object(
      test_try_job, 'FindCulpritForEachTestFailure', return_value=({}, []))
  @mock.patch.object(test_try_job, 'UpdateTryJobResult')
  @mock.patch.object(
      build_failure_analysis, 'GetHeuristicSuspectedCLs', return_value=[])
  @mock.patch.object(test_try_job, 'UpdateWfAnalysisWithTryJobResult')
  @mock.patch.object(test_try_job, 'UpdateSuspectedCLs')
  def testIdentifyTestTryJobCulpritsNoCulprit(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    culprits, _ = test_try_job.IdentifyTestTryJobCulprits(
        master_name, builder_name, build_number, try_job_id, test_result)
    self.assertEqual({}, culprits)

  def testIdentifyTestTryJobCulpritsNoResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    test_result = None

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        test_results=[test_result])

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    culprits, _ = test_try_job.IdentifyTestTryJobCulprits(
        master_name, builder_name, build_number, try_job_id, test_result)
    self.assertIsNone(culprits)

  @mock.patch.object(
      waterfall_config, 'GetWaterfallTrybot', return_value=('m', 'b'))
  @mock.patch.object(test_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(try_job_service, 'TriggerTryJob', return_value=('1', None))
  def testSuccessfullyScheduleNewTryJobForTest(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}
    build_id = '1'
    WfTryJob.Create(master_name, builder_name, build_number).put()

    parameters = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False)

    try_job_id = test_try_job.ScheduleTestTryJob(parameters, 'pipeline')

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job_id, build_id)
    self.assertEqual(try_job.test_results[-1]['try_job_id'], build_id)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.master_name, master_name)
    self.assertEqual(try_job_data.builder_name, builder_name)
    self.assertEqual(try_job_data.build_number, build_number)
    self.assertEqual(
        try_job_data.try_job_type,
        failure_type.GetDescriptionForFailureType(failure_type.TEST))
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertFalse(try_job_data.has_heuristic_results)

  class MockedError(object):

    def __init__(self, message, reason):
      self.message = message
      self.reason = reason

  @mock.patch.object(
      waterfall_config, 'GetWaterfallTrybot', return_value=('m', 'b'))
  @mock.patch.object(test_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(
      try_job_service,
      'TriggerTryJob',
      return_value=(None, MockedError('message', 'reason')))
  def testScheduleTestTryJobRaise(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    parameters = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False)

    with self.assertRaises(exceptions.RetryException):
      test_try_job.ScheduleTestTryJob(parameters, 'pipeline')
