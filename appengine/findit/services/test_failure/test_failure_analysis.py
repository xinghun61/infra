# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a function to analyze test failures."""

from collections import defaultdict

from common.findit_http_client import FinditHttpClient
from model.wf_analysis import WfAnalysis
from services import build_failure_analysis
from services import ci_failure
from services import deps
from services import git
from services.test_failure import extract_test_signal
from waterfall.failure_signal import FailureSignal


def _AnalyzeTestFailureOnOneBuild(build_number,
                                  step_name,
                                  test_name,
                                  failure_signal,
                                  change_log,
                                  deps_info,
                                  step_analysis_result,
                                  cl_failure_map,
                                  has_lower_level_info=False):

  new_suspected_cl_dict, max_score = build_failure_analysis.AnalyzeOneCL(
      build_number, failure_signal, change_log, deps_info)

  if not new_suspected_cl_dict:
    return

  step_analysis_result['suspected_cls'].append(new_suspected_cl_dict)

  if not has_lower_level_info:
    build_failure_analysis.SaveFailureToMap(
        cl_failure_map, new_suspected_cl_dict, step_name, test_name, max_score)


def AnalyzeTestFailure(failure_info, change_logs, deps_info, failure_signals):
  """Analyzes given failure signals, and figure out culprits of test failure.

  Args:
    failure_info (dict): Output of pipeline DetectFirstFailurePipeline.
    change_logs (dict): Output of pipeline PullChangelogPipeline.
    deps_info (dict): Output of pipeline ExtractDEPSInfoPipeline.
    failure_signals (dict): Output of pipeline ExtractSignalPipeline.

  Returns:
    A dict with the following form:
    {
      'failures': [
        {
          'step_name': 'compile',
          'supported': True
          'first_failure': 230,
          'last_pass': 229,
          'suspected_cls': [
            {
              'build_number': 230,
              'repo_name': 'chromium',
              'revision': 'a_git_hash',
              'commit_position': 56789,
              'score': 11,
              'hints': {
                'add a/b/x.cc': 5,
                'delete a/b/y.cc': 5,
                'modify e/f/z.cc': 1,
                ...
              }
            },
            ...
          ],
        },
        ...
      ]
    }

    And a list of suspected_cls format as below:
    [
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            'top_score': 4
        },
        ...
    ]
  """
  analysis_result = {'failures': []}

  failed_steps = failure_info['failed_steps']
  builds = failure_info['builds']
  master_name = failure_info['master_name']

  cl_failure_map = defaultdict(build_failure_analysis.CLInfo)

  for step_name, step_failure_info in failed_steps.iteritems():
    is_test_level = step_failure_info.get('tests') is not None

    failed_build_number = step_failure_info['current_failure']
    start_build_number = (
        build_failure_analysis.GetLowerBoundForAnalysis(step_failure_info))
    step_analysis_result = (build_failure_analysis.InitializeStepLevelResult(
        step_name, step_failure_info, master_name))

    if is_test_level:
      step_analysis_result['tests'] = []
      for test_name, test_failure in step_failure_info['tests'].iteritems():
        test_analysis_result = {
            'test_name': test_name,
            'first_failure': test_failure['first_failure'],
            'last_pass': test_failure.get('last_pass'),
            'suspected_cls': [],
        }
        step_analysis_result['tests'].append(test_analysis_result)

    if step_analysis_result['supported']:
      step_failure_signal = FailureSignal.FromDict(failure_signals[step_name])
      for build_number in range(start_build_number, failed_build_number + 1):
        for revision in builds[build_number]['blame_list']:
          if is_test_level:
            # Checks files at test level.
            for test_analysis_result in step_analysis_result['tests']:
              test_name = test_analysis_result['test_name']
              test_signal = FailureSignal.FromDict(
                  failure_signals[step_name]['tests'].get(test_name, {}))

              _AnalyzeTestFailureOnOneBuild(build_number, step_name, test_name,
                                            test_signal, change_logs[revision],
                                            deps_info, test_analysis_result,
                                            cl_failure_map)

          # Checks Files on step level using step level signals
          # regardless of test level signals so we can make sure
          # no duplicate justifications added to the step result.
          _AnalyzeTestFailureOnOneBuild(
              build_number,
              step_name,
              None,
              step_failure_signal,
              change_logs[revision],
              deps_info,
              step_analysis_result,
              cl_failure_map,
              has_lower_level_info=is_test_level)

    # TODO(stgao): sort CLs by score.
    analysis_result['failures'].append(step_analysis_result)

  suspected_cls = build_failure_analysis.ConvertCLFailureMapToList(
      cl_failure_map)

  return analysis_result, suspected_cls


def HeuristicAnalysisForTest(failure_info, build_completed):
  """Identifies culprit CL.

      Args:
        failure_info (dict): A dict of failure info for the current failed build
          in the following form:
        {
          "master_name": "chromium.gpu",
          "builder_name": "GPU Linux Builder"
          "build_number": 25410,
          "failed": true,
          "failed_steps": {
            "test": {
              "current_failure": 25410,
              "first_failure": 25410
            }
          },
          "builds": {
            "25410": {
              "chromium_revision": "4bffcd598dd89e0016208ce9312a1f477ff105d1"
              "blame_list": [
                "b98e0b320d39a323c81cc0542e6250349183a4df",
                ...
              ],
            }
          }
        }
        build_completed (bool): If the build is completed.

      Returns:
        A dict in below format:
        {
            'failure_info': failure_info,
            'heuristic_result': heuristic_result
        }
      """
  master_name = failure_info['master_name']
  builder_name = failure_info['builder_name']
  build_number = failure_info['build_number']

  # 1. Detects first failed builds for failed test step, updates failure_info.
  failure_info = ci_failure.CheckForFirstKnownFailure(
      master_name, builder_name, build_number, failure_info)

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.failure_info = failure_info
  analysis.put()

  # 2. Extracts failure signal.
  signals = extract_test_signal.ExtractSignalsForTestFailure(
      failure_info, FinditHttpClient())

  # 3. Gets change_logs.
  change_logs = git.PullChangeLogs(failure_info)

  # 4. Gets deps info.
  deps_info = deps.ExtractDepsInfo(failure_info, change_logs)

  # 5. Analyzes the test failure using information collected above.
  heuristic_result, suspected_cls = AnalyzeTestFailure(
      failure_info, change_logs, deps_info, signals)

  # Save results and other info to analysis.
  build_failure_analysis.SaveAnalysisAfterHeuristicAnalysisCompletes(
      master_name, builder_name, build_number, build_completed,
      heuristic_result, suspected_cls)

  # Save suspected_cls to data_store.
  build_failure_analysis.SaveSuspectedCLs(
      suspected_cls, failure_info['master_name'], failure_info['builder_name'],
      failure_info['build_number'], failure_info['failure_type'])
  return {'failure_info': failure_info, 'heuristic_result': heuristic_result}
