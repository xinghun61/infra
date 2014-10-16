# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import json

from infra.tools.builder_alerts import analysis

class FailureAnalysisTest(unittest.TestCase):
  # v8 stays the same, chromium differs, nacl is reduced.
  MERGE_REGRESSION_RANGES_JSON = """
[
    {
     "failing_revisions": {
      "v8": "22263",
      "chromium": "282006",
      "nacl": "13441"
     },
     "passing_revisions": {
      "v8": "22263",
      "chromium": "281980",
      "nacl": "13441"
     }
    },
    {
     "failing_revisions": {
      "v8": "22263",
      "chromium": "282022",
      "nacl": "13452"
     },
     "passing_revisions": {
      "v8": "22263",
      "chromium": "281989",
      "nacl": "13441"
     }
    }
]
"""

  MERGE_REGRESSION_RANGES_JSON_NULL = """
[
    {
     "failing_revisions": {
      "v8": "22263",
      "nacl": "13441"
     },
     "passing_revisions": null
    },
    {
     "failing_revisions": {
      "v8": "22263",
      "nacl": null
     },
     "passing_revisions": {
      "v8": "22263",
      "nacl": "13441"
     }
    }
]
"""

  def test_merge_regression_ranges(self):
    alerts = json.loads(self.MERGE_REGRESSION_RANGES_JSON)
    passing, failing = analysis.merge_regression_ranges(alerts)
    expected_pass = { 'v8': '22263', 'chromium': '281989', 'nacl': '13441' }
    expected_fail = { 'v8': '22263', 'chromium': '282006', 'nacl': '13441' }
    self.assertEquals(expected_fail, failing)
    self.assertEquals(expected_pass, passing)

    alerts = json.loads(self.MERGE_REGRESSION_RANGES_JSON_NULL)
    passing, failing = analysis.merge_regression_ranges(alerts)
    expected_pass = None
    expected_fail = { 'v8': '22263', 'nacl': '13441' }
    self.assertEquals(expected_fail, failing)
    self.assertEquals(expected_pass, passing)


  def test_flatten_to_commit_list(self):
    passing = { 'v8': '1', 'chromium': '4'}
    failing = { 'v8': '2', 'chromium': '4'}
    commit_list = analysis.flatten_to_commit_list(passing, failing)
    self.assertEquals(commit_list, ['v8:2'])
    self.assertEquals(analysis.flatten_to_commit_list(passing, []), [])
    self.assertEquals(analysis.flatten_to_commit_list([], failing), [])

  def test_range_key_for_group(self):
    failing = { 'v8': '2', 'chromium': '4'}
    group = {
        'merged_last_passing': None,
        'merged_first_failing': failing,
        'sort_key': 'foobar',
    }
    range_key = analysis.range_key_for_group(group)
    self.assertEquals(range_key, 'foo<=v8:2 <=chromium:4')

  def test_range_key_for_group_no_first_failure(self):
    group = {
        'merged_last_passing': None,
        'merged_first_failing': None,
        'sort_key': 'foobar',
    }
    range_key = analysis.range_key_for_group(group)
    self.assertEquals(range_key, 'foono_first_failing')

  MERGE_BY_RANGE_JSON = """
[
  {
   "merged_last_passing": { "v8": "1" },
   "merged_first_failing": { "v8": "2" },
   "sort_key": "dromaeo.domcoreattr",
   "failure_keys": [
   ]
  },
  {
   "merged_last_passing": { "v8": "1" },
   "merged_first_failing": { "v8": "2" },
   "sort_key": "dromaeo.jslibmodifyprototype",
   "failure_keys": [
   ]
  }
]
"""

  def test_merge_by_range(self):
    groups = json.loads(self.MERGE_BY_RANGE_JSON)
    merged = analysis.merge_by_range(groups)
    self.assertEqual(len(merged), 1)
    self.assertEqual(merged[0]['sort_key'], 'dromaeo.')
    self.assertEqual(analysis.merge_by_range([]), [])

  def test_assign_keys(self):
    alerts = [ { 'foo': 1 }, { 'foo': 1 } ]
    alerts = analysis.assign_keys(alerts)
    # keys assigned...
    self.assertIn('key', alerts[0])
    self.assertIn('key', alerts[1])
    # and distinct
    self.assertNotEqual(alerts[0]['key'], alerts[1]['key'])

  def test_reason_key_for_alert(self):
    def alert(step, builder, reason=None):
      return {'step_name': step, 'builder_name': builder, 'reason': reason}
    a0 = alert('s0', 'b0', 'r0')
    a1 = alert('s0', 'b0', 'r0')
    a2 = alert('s0', 'b0')
    a3 = alert('s0', 'b1', 'r0')
    a4 = alert('s0', 'b1')
    a5 = alert('s0', 'b0', 'r1')
    f = analysis.reason_key_for_alert
    self.assertEqual(f(a0), f(a1)) # equal s/b/r -> equal key
    self.assertEqual(f(a0), f(a3)) # equal s/r -> equal key
    self.assertNotEqual(f(a0), f(a2)) # r vs no r -> different key
    self.assertNotEqual(f(a2), f(a4)) # different s/b -> different key
    self.assertNotEqual(f(a3), f(a4)) # r vs no r -> different key
    self.assertNotEqual(f(a0), f(a5)) # different r -> different key

  def test_ids_after_first(self):
    f = analysis.ids_after_first_including_second
    # invalid range endpoints yield []
    self.assertEqual([], f(0, 5))
    self.assertEqual([], f(5, 0))
    # valid endpoints (a,b) yield (a, b]
    self.assertEqual([2, 3, 4, 5], f(1, 5))
    c0 = '4fcb9c951929b41e7e489c90889a00a1c7214cfd'
    c1 = '10caabc60b70832f702e200d9fd0a06be061317d'
    # git commit-ids currently unsupported
    self.assertEqual([], f(c0, c1))
