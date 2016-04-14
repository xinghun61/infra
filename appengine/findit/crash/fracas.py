# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Process crashes from Chrome crash server and find culprits for them."""


def FindCulpritForChromeCrash(  # Not implemented yet pylint: disable=W0613
    channel, platform, signature, stack_trace,
    crashed_version, versions_to_cpm):
  """Finds culprits for a Chrome crash.

  Args:
    channel (str): The channel name, could be 'dev', 'canary', 'beta', etc.
    platform (str): The platform name, could be 'win', 'mac', 'linux',
        'android', 'ios', etc.
    signature (str): The signature of a crash on the Chrome crash server.
    stack_trace (str): A string containing the stack trace of a crash.
    crash_version (str): The version of Chrome in which the crash occurred.
    versions_to_cpm (dict): Mapping from Chrome version to crash per million
        page loads.

  Returns:
    (analysis_result_dict, tag_dict)
    The analysis result is a dict like below:
      {
        "found": True,  # Indicate whether anything is found.
        "suspected_project_path": "src/v8",  # The full path to the dependency.
        "suspected_project_name": "v8",  # A project name of the dependency.
        "components": ["blink>javascript"],  # Components to file bug against.
        "culprits": [
          {
            "url": "https://chromium.googlesource.com/chromium/.../+/hash",
            "revision": "commit-hash",
            "code_review_url": "https://codereview.chromium.org/ISSUE",
            "project_path": "src/v8",
            "project_name": "v8",
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
      For results with normal culprit-finding algorithm:
        {
          'found_suspects': True,
          'has_regression_range': True,
          'solution': 'core_algorithm',
        }
      For results using git blame without a regression range:
        {
          'found_suspects': True,
          'has_regression_range': False,
          'solution': 'blame',
        }
      If nothing is found:
        {
          'found_suspects': False,
        }
  """
  # TODO (katesonia): hook the analysis logic up here.
  return {'found': False}, {'found_suspects': False}  # pragma: no cover.
