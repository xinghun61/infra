# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Util functions for disabled test detection handlers."""

import re

from model.flake.flake_issue import FlakeIssue

DEFAULT_PAGE_SIZE = 100
_TEST_FILTER_NAME = 'test'

_OS_REGEX_PATTERN_MAPPING = [(re.compile('os:mac', re.I), 'os:Mac'),
                             (re.compile('os:linux', re.I), 'os:linux'),
                             (re.compile('os:ubuntu', re.I), 'os:linux'),
                             (re.compile('os:android', re.I), 'os:Android'),
                             (re.compile('os:chromeos', re.I), 'os:ChromeOS'),
                             (re.compile('os:windows', re.I), 'os:Windows'),
                             (re.compile('os:ios', re.I), 'os:iOS')]


def _NormalizeOS(os):
  for pattern, normalized_os in _OS_REGEX_PATTERN_MAPPING:
    if pattern.search(os):
      return normalized_os
  return os


def _SummarizeDisabledVariants(disabled_test_variants):
  """Summarizes disabled_test_variants in order to be displayed on dashboard.

  Currently only supports consolidation of the os. For example:
  - os:Mac, MSan:True
  Instead of
  - os:Mac 10-11, MSan:True
  - os:Mac 13-10, MSan:True

  Args:
    disabled_test_variants (set of string tuples): The disabled test variant as
      found in the datastore.

  Returns:
    disabled_test_variants ([[str]]): The summarized disabled test variants.
  """
  analyzed_disabled_test_variants = set()
  for variant in disabled_test_variants:
    variant = list(variant)
    for index, configuration in enumerate(variant):
      if configuration.startswith('os'):
        variant[index] = _NormalizeOS(configuration)
    variant = tuple(variant)
    analyzed_disabled_test_variants.add(variant)

  return [list(variant) for variant in analyzed_disabled_test_variants]


def GenerateDisabledTestsData(disabled_tests):
  """Processes disabled test data to make them ready to be displayed on pages.

  Args:
    disabled_tests ([LuciTest]): A list of LuciTest entities.

  Returns:
    [dict]: A list of dicts containing each disabled test's data.
      Dictionaries are of the format:
      {
        'luci_project' : str,
        'normalized_step_name': str,
        'normalized_test_name': str,
        'disabled_test_variants': [[str]],
        'disabled': bool,
        'issue_keys: [ndb.Key],
        'issues': [
          {
          'issue_id': str,
          'issue_link': str,
          },
        ]
        'tags': [str],
        'last_updated_time': datetime,
      }
  """
  disabled_tests_data = []
  for disabled_test in disabled_tests:
    disabled_test_dict = disabled_test.to_dict()
    disabled_test_dict['disabled_test_variants'] = _SummarizeDisabledVariants(
        disabled_test_dict['disabled_test_variants'])
    disabled_test_dict['issues'] = []
    for issue_key in disabled_test.issue_keys:
      issue = issue_key.get()
      if not issue:
        continue
      issue_dict = {
          'issue_link':
              FlakeIssue.GetLinkForIssue(issue.monorail_project,
                                         issue.issue_id),
          'issue_id':
              issue.issue_id
      }
      disabled_test_dict['issues'].append(issue_dict)
    disabled_tests_data.append(disabled_test_dict)
  return disabled_tests_data
