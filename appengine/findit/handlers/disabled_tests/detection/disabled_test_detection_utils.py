# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Util functions for disabled test detection handlers."""

from model.flake.flake_issue import FlakeIssue
from model.test_inventory import LuciTest

DEFAULT_PAGE_SIZE = 100
_TEST_FILTER_NAME = 'test'


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
    disabled_test_dict[
        'disabled_test_variants'] = LuciTest.SummarizeDisabledVariants(
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
