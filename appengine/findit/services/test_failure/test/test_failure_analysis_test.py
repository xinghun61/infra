# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from libs.gitiles.diff import ChangeType
from model.wf_analysis import WfAnalysis
from services import build_failure_analysis
from services import ci_failure
from services import deps
from services import git
from services.test_failure import extract_test_signal
from services.test_failure import test_failure_analysis
from waterfall.test import wf_testcase


class TestFailureAnalysisTest(wf_testcase.WaterfallTestCase):

  def testAnalyzeTestFailure(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.TEST,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'a': {
                'current_failure': 99,
                'first_failure': 98,
            },
            'b': {
                'current_failure': 99,
                'first_failure': 98,
                'last_pass': 96,
            },
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            },
            97: {
                'blame_list': ['r97_1'],
            },
            96: {
                'blame_list': ['r96_1', 'r96_2'],
            },
        }
    }
    change_logs = {
        'r99_1': {
            'revision':
                'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r99_2': {
            'revision':
                'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r98_1': {
            'revision':
                'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r97_1': {
            'revision':
                'r97_1',
            'touched_files': [
                {
                    'change_type': ChangeType.ADD,
                    'old_path': '/dev/null',
                    'new_path': 'x/y/f99_1.cc'
                },
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r96_1': {
            'revision':
                'r96_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f96_1.cc',
                    'new_path': 'a/b/f96_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
    }
    deps_info = {}
    failure_signals_json = {
        'a': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        },
        'b': {
            'files': {
                'x/y/f99_1.cc': [],
            },
        },
    }
    expected_analysis_result = {
        'failures': [{
            'step_name':
                'a',
            'supported':
                True,
            'first_failure':
                98,
            'last_pass':
                None,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    'modified f99_2.cc (and it was in log)': 2,
                },
            }],
        }, {
            'step_name':
                'b',
            'supported':
                True,
            'first_failure':
                98,
            'last_pass':
                96,
            'suspected_cls': [{
                'build_number': 97,
                'repo_name': 'chromium',
                'revision': 'r97_1',
                'commit_position': None,
                'url': None,
                'score': 5,
                'hints': {
                    'added x/y/f99_1.cc (and it was in log)': 5,
                },
            }],
        }]
    }

    expected_suspected_cl = [{
        'repo_name': 'chromium',
        'revision': 'r99_2',
        'commit_position': None,
        'url': None,
        'failures': {
            'a': []
        },
        'top_score': 2
    }, {
        'repo_name': 'chromium',
        'revision': 'r97_1',
        'commit_position': None,
        'url': None,
        'failures': {
            'b': []
        },
        'top_score': 5
    }]

    analysis_result, suspected_cls = (test_failure_analysis.AnalyzeTestFailure(
        failure_info, change_logs, deps_info, failure_signals_json))

    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  def testAnalyzeTestFailureTestLevel(self):
    failure_info = {
        'failed': True,
        'chromium_revision': 'r99_2',
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.TEST,
        'failed_steps': {
            'a': {
                'current_failure': 99,
                'first_failure': 98,
            },
            'b': {
                'current_failure':
                    99,
                'first_failure':
                    98,
                'last_pass':
                    96,
                'list_isolated_data': [{
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }],
                'tests': {
                    'Unittest1.Subtest1': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 97
                    },
                    'Unittest2.Subtest1': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 97
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 96
                    },
                    'Unittest3.Subtest3': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 96
                    }
                }
            },
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            },
            97: {
                'blame_list': ['r97_1'],
            },
            96: {
                'blame_list': ['r96_1', 'r96_2'],
            },
        }
    }
    change_logs = {
        'r99_1': {
            'revision':
                'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r99_2': {
            'revision':
                'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r98_1': {
            'revision':
                'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r97_1': {
            'revision':
                'r97_1',
            'touched_files': [
                {
                    'change_type': ChangeType.ADD,
                    'old_path': '/dev/null',
                    'new_path': 'x/y/f99_1.cc'
                },
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r96_1': {
            'revision':
                'r96_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f96_1.cc',
                    'new_path': 'a/b/f96_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
    }
    deps_info = {}
    failure_signals_json = {
        'a': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        },
        'b': {
            'files': {
                'x/y/f99_1.cc': [],
                'y/z/f98.cc': [123, 456],
            },
            'tests': {
                'Unittest1.Subtest1': {
                    'files': {
                        'x/y/f99_1.cc': [],
                    },
                },
                'Unittest2.Subtest1': {
                    'files': {
                        'y/z/f98.cc': [123],
                    },
                },
                'Unittest3.Subtest2': {
                    'files': {
                        'y/z/f98.cc': [456],
                    },
                }
            }
        }
    }

    def MockGetChangedLines(repo_info, touched_file, line_numbers, _):
      # Only need line_numbers, ignoring the first two parameters.
      del repo_info, touched_file
      if line_numbers:
        return line_numbers

    self.mock(build_failure_analysis, '_GetChangedLinesForChromiumRepo',
              MockGetChangedLines)

    expected_analysis_result = {
        'failures': [{
            'step_name':
                'a',
            'first_failure':
                98,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    'modified f99_2.cc (and it was in log)': 2,
                },
            }],
        }, {
            'step_name':
                'b',
            'first_failure':
                98,
            'last_pass':
                96,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 97,
                'repo_name': 'chromium',
                'revision': 'r97_1',
                'commit_position': None,
                'url': None,
                'score': 5,
                'hints': {
                    'added x/y/f99_1.cc (and it was in log)': 5,
                },
            }, {
                'build_number': 98,
                'repo_name': 'chromium',
                'revision': 'r98_1',
                'commit_position': None,
                'url': None,
                'score': 4,
                'hints': {
                    'modified f98.cc[123, 456] (and it was in log)': 4,
                },
            }],
            'tests': [{
                'test_name':
                    'Unittest1.Subtest1',
                'first_failure':
                    98,
                'last_pass':
                    97,
                'suspected_cls': [{
                    'build_number': 97,
                    'repo_name': 'chromium',
                    'revision': 'r97_1',
                    'commit_position': None,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    },
                }]
            }, {
                'test_name':
                    'Unittest2.Subtest1',
                'first_failure':
                    98,
                'last_pass':
                    97,
                'suspected_cls': [{
                    'build_number': 98,
                    'repo_name': 'chromium',
                    'revision': 'r98_1',
                    'commit_position': None,
                    'url': None,
                    'score': 4,
                    'hints': {
                        ('modified f98.cc[123] '
                         '(and it was in log)'): 4,
                    },
                }]
            }, {
                'test_name':
                    'Unittest3.Subtest2',
                'first_failure':
                    98,
                'last_pass':
                    96,
                'suspected_cls': [{
                    'build_number': 98,
                    'repo_name': 'chromium',
                    'revision': 'r98_1',
                    'commit_position': None,
                    'url': None,
                    'score': 4,
                    'hints': {
                        ('modified f98.cc[456] '
                         '(and it was in log)'): 4,
                    },
                }]
            }, {
                'test_name': 'Unittest3.Subtest3',
                'first_failure': 98,
                'last_pass': 96,
                'suspected_cls': []
            }]
        }]
    }

    expected_suspected_cl = [{
        'repo_name': 'chromium',
        'revision': 'r99_2',
        'commit_position': None,
        'url': None,
        'failures': {
            'a': []
        },
        'top_score': 2
    }, {
        'repo_name': 'chromium',
        'revision': 'r97_1',
        'commit_position': None,
        'url': None,
        'failures': {
            'b': ['Unittest1.Subtest1']
        },
        'top_score': 5
    }, {
        'repo_name': 'chromium',
        'revision': 'r98_1',
        'commit_position': None,
        'url': None,
        'failures': {
            'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
        },
        'top_score': 4
    }]

    analysis_result, suspected_cls = (test_failure_analysis.AnalyzeTestFailure(
        failure_info, change_logs, deps_info, failure_signals_json))

    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  def testAnalyzeTestFailureForUnsupportedStep(self):
    failure_info = {
        'master_name': 'master1',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.TEST,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'unsupported_step1': {
                'current_failure': 99,
                'first_failure': 98,
            },
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            },
        }
    }
    change_logs = {}
    deps_info = {}
    failure_signals_json = {
        'not_supported': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        }
    }
    expected_analysis_result = {
        'failures': [
            {
                'step_name': 'unsupported_step1',
                'supported': False,
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [],
            },
        ]
    }

    analysis_result, suspected_cls = (test_failure_analysis.AnalyzeTestFailure(
        failure_info, change_logs, deps_info, failure_signals_json))
    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual([], suspected_cls)

  @mock.patch.object(
      extract_test_signal,
      'ExtractSignalsForTestFailure',
      return_value='signals')
  @mock.patch.object(git, 'PullChangeLogs', return_value={})
  @mock.patch.object(deps, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(
      test_failure_analysis,
      'AnalyzeTestFailure',
      return_value=('heuristic_result', []))
  @mock.patch.object(build_failure_analysis,
                     'SaveAnalysisAfterHeuristicAnalysisCompletes')
  @mock.patch.object(build_failure_analysis, 'SaveSuspectedCLs')
  @mock.patch.object(ci_failure, 'CheckForFirstKnownFailure')
  def testHeuristicAnalysisForTest(self, mock_failure_info, *_):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.COMPILE,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'test': {
                'current_failure': 99,
                'first_failure': 98,
            }
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            }
        }
    }

    mock_failure_info.return_value = failure_info
    WfAnalysis.Create('m', 'b', 99).put()
    result = test_failure_analysis.HeuristicAnalysisForTest(failure_info, True)
    expected_result = {
        'failure_info': failure_info,
        'heuristic_result': 'heuristic_result'
    }
    self.assertEqual(result, expected_result)
