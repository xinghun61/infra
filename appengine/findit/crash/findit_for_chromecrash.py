# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Process crashes from Chrome crash server and find culprits for them."""

import logging

from common import chromium_deps
from crash import detect_regression_range
from crash import findit_for_crash
from crash.fracas_parser import FracasParser
from crash.project_classifier import ProjectClassifier
from crash.component import Component
from crash.component_classifier import ComponentClassifier
from model.crash.crash_config import CrashConfig

# TODO(katesonia): Remove the default value after adding validity check to
# config.
_DEFAULT_TOP_N = 7


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
        # Indicate if Findit found any suspects_cls, suspected_project,
        # suspected_components or regression_range.
        "found": true,
        "suspected_project": "chromium-v8",  # Which project is most suspected.
        "feedback_url": "https://.."
        "suspected_cls": [
            {
                "revision": "commit-hash",
                "url": "https://chromium.googlesource.com/chromium/src/+/ha...",
                "review_url": "https://codereview.chromium.org/issue-number",
                "project_path": "third_party/pdfium",
                "author": "who@chromium.org",
                "time": "2015-08-17 03:38:16",
                "reason": "a plain string with '\n' as line break to explain..."
                "reason": [('MinDistance', 1, 'minimum distance is 0.'),
                           ('TopFrame', 0.9, 'top frame is2nd frame.')],
                "changed_files": [
                    {"file": "file_name1.cc",
                     "blame_url": "https://...",
                     "info": "minimum distance (LOC) 0, frame #2"},
                    {"file": "file_name2.cc",
                     "blame_url": "https://...",
                     "info": "minimum distance (LOC) 20, frame #4"},
                    ...
                ],
                "confidence": 0.60
            },
            ...,
        ],
        "regression_range": [  # Detected regression range.
            "53.0.2765.0",
            "53.0.2766.0"
        ],
        "suspected_components": [  # A list of crbug components to file bugs.
            "Blink>JavaScript"
        ]
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
  if not stacktrace:
    logging.warning('Failed to parse the stacktrace %s', stack_trace)
    return {'found': False}, {'found_suspects': False,
                              'has_regression_range': False}

  regression_deps_rolls = {}
  regression_versions = detect_regression_range.DetectRegressionRange(
      historic_metadata)

  if regression_versions:
    last_good_version, first_bad_version = regression_versions
    logging.info('Find regression range %s:%s', last_good_version,
                 first_bad_version)

    # Get regression deps and crash deps.
    dep_rolls = chromium_deps.GetDEPSRollsDict(
        last_good_version, first_bad_version, platform)

    # Regression of a dep added/deleted (old_revision/new_revision is None) can
    # not be known for sure and this case rarely happens, so just filter them
    # out.
    for dep_path, dep_roll in dep_rolls.iteritems():
      if not dep_roll.old_revision or not dep_roll.new_revision:
        continue
      regression_deps_rolls[dep_path] = dep_roll

  crash_config = CrashConfig.Get()
  culprit_results = findit_for_crash.FindItForCrash(
      stacktrace, regression_deps_rolls, crash_deps, crash_config.fracas.get(
          'top_n', _DEFAULT_TOP_N))

  crash_stack = stacktrace.crash_stack
  suspected_project = ProjectClassifier().Classify(
      culprit_results, crash_stack)

  component_classifier_config = CrashConfig.Get().compiled_component_classifier
  suspected_components = ComponentClassifier(
      # TODO(wrengr): have the config return Component objects directly,
      # rather than needing to convert them here.
      [Component(component_name, path_regex, function_regex)
          for path_regex, function_regex, component_name
          in component_classifier_config['path_function_component']],
      component_classifier_config['top_n']
    ).Classify(culprit_results, crash_stack)

  # TODO(http://crbug.com/644411): the caller should convert things to
  # JSON, not us.
  culprit_results_list = [result.ToDict() for result in culprit_results]

  return (
      {
          'found': (bool(suspected_project) or bool(suspected_components) or
                    bool(culprit_results_list) or bool(regression_versions)),
          'regression_range': regression_versions,
          'suspected_project': suspected_project,
          'suspected_components': suspected_components,
          'suspected_cls': culprit_results_list,
      },
      {
          'found_suspects': bool(culprit_results_list),
          'found_project': bool(suspected_project),
          'found_components': bool(suspected_components),
          'has_regression_range': bool(regression_versions),
          'solution': 'core_algorithm',
      }
  )
