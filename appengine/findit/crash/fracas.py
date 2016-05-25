# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Process crashes from Chrome crash server and find culprits for them."""

from common import chromium_deps
from crash import detect_regression_range
from crash import findit_for_crash
from crash.fracas_parser import FracasParser
from crash.project_classifier import ProjectClassifier
from crash.component_classifier import ComponentClassifier


def FindCulpritForChromeCrash(signature, platform,
                              stack_trace, crashed_version, historic_metadata):
  """Finds culprits for a Chrome crash.

  Args:
    platform (str): The platform name, could be 'win', 'mac', 'linux',
      'android', 'ios', etc.
    signature (str): The signature of a crash on the Chrome crash server.
    stack_trace (str): A string containing the stack trace of a crash.
    crash_version (str): The version of Chrome in which the crash occurred.
    historic_metadata (list): list of dicts mapping from Chrome version to
      historic metadata.

  Returns:
    (analysis_result_dict, tag_dict)
    The analysis result is a dict like below:
      {
        "found": True,  # Indicate whether anything is found.
        "suspected_project": "src/v8",  # The full path to the dependency.
        # Components to file bug against.
        "suspected_components": ["blink>javascript"],
        "culprits": [
          {
            "url": "https://chromium.googlesource.com/chromium/.../+/hash",
            "revision": "commit-hash",
            "code_review_url": "https://codereview.chromium.org/ISSUE",
            "project_path": "src/v8",
            "author": "who@chromium.org",
            "time": "2015-08-17 03:38:16",  # When the revision was committed.
            "reason": "A plain string with '\n' as line break to explain why",
            "confidence": "0.6",  # Optional confidence score.
          },
        ],
      }
    The code review url might not always be available, because not all commits
    go through code review. In that case, commit url should be used instead.

    The tag dict are allowed key/value pairs to tag the analysis result for
    query and monitoring purpose on Findit side. For allowed keys, please
    refer to crash_analysis.py and fracas_crash_analysis.py:
      For results with normal culprit-finding algorithm: {
          'found_suspects': True,
          'has_regression_range': True,
          'solution': 'core_algorithm',
      }
      For results using git blame without a regression range: {
          'found_suspects': True,
          'has_regression_range': False,
          'solution': 'blame',
      }
      If nothing is found: {
          'found_suspects': False,
      }
  """
  crash_deps = chromium_deps.GetChromeDependency(crashed_version, platform)
  stacktrace = FracasParser().Parse(stack_trace, crash_deps, signature)

  regression_deps_rolls = {}
  regression_versions = detect_regression_range.DetectRegressionRange(
      historic_metadata)

  if regression_versions:
    last_good_version, first_bad_version = regression_versions
    # Get regression deps and crash deps.
    regression_deps_rolls = chromium_deps.GetDEPSRollsDict(
        last_good_version, first_bad_version, platform)

  culprit_results = findit_for_crash.FindItForCrash(
      stacktrace, regression_deps_rolls, crash_deps)

  crash_stack = stacktrace.crash_stack
  suspected_project = ProjectClassifier().Classify(
      culprit_results, crash_stack)
  suspected_components = ComponentClassifier().Classify(
      culprit_results, crash_stack)

  return (
      {
          'found': (bool(suspected_project) or bool(suspected_components) or
                    bool(culprit_results)),
          'suspected_project': suspected_project,
          'suspected_components': suspected_components,
          'culprits': culprit_results,
      },
      {
          'found_suspects': bool(culprit_results),
          'has_regression_range': bool(regression_versions),
          'solution': 'core_algorithm',
      }
  )
