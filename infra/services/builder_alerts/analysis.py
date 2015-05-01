# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import operator
import logging

from infra.services.builder_alerts import string_helpers


# Git ready, but only implemented for SVN atm.
def ids_after_first_including_second(first, second):
  if not first or not second:
    return []
  try:
    return range(int(first) + 1, int(second) + 1)
  except ValueError:
    # likely passed a git hash
    return []


# Git ready, but only implemented for SVN atm.
def is_ancestor_of(older, younger):
  return int(older) < int(younger)


def is_descendant_of(younger, older):
  return is_ancestor_of(older, younger)


def flatten_to_commit_list(passing, failing):
  # Flatten two commit dicts to a list of 'name:commit'
  if not passing or not failing:
    return []
  all_commits = []
  for name in passing.keys():
    commits = ids_after_first_including_second(passing[name], failing[name])
    all_commits.extend(['%s:%s' % (name, commit) for commit in commits])
  return all_commits


# FIXME: Perhaps this should be done by the feeder?
def assign_keys(alerts):
  """Assign identifying keys to each alert in alerts.

  Keys must be comparable for sorting, but can otherwise have arbitrary
  structure.
  """
  for key, alert in enumerate(alerts):
    # We could come up with something more sophisticated if necessary.
    # Just something so it doesn't look like a number
    alert['key'] = 'f%s' % key
  return alerts


def _make_merge_dicts(reducer):
  def merge_dicts(one, two):
    if not one or not two:
      return None
    reduction = {}
    for key in set(one.keys() + two.keys()):
      one_value = one.get(key)
      two_value = two.get(key)
      reduction[key] = reducer(one_value, two_value)
    return reduction
  return merge_dicts


def merge_regression_ranges(alerts):
  def make_compare(compare_func):
    def compare(one, two):
      if one and two and compare_func(one, two):
        return one
      # Treat None is 'infinite' so always return the more limiting.
      # FIXME: 'passing' may wish to prefer None over a value?
      return two or one
    return compare

  # These don't handle the case where commits can't be compared (git branches)
  younger_commit = make_compare(is_descendant_of)
  passing_dicts = map(operator.itemgetter('passing_revisions'), alerts)
  last_passing = reduce(_make_merge_dicts(younger_commit), passing_dicts)

  older_commit = make_compare(is_ancestor_of)
  failing_dicts = map(operator.itemgetter('failing_revisions'), alerts)
  first_failing = reduce(_make_merge_dicts(older_commit), failing_dicts)

  # FIXME: Ojan would like us to remove keys from both last and first
  # in the case where last > first.  Unfortunately that's somewhat
  # tricky to do here.  It happens that flatten_to_commit_list
  # happens to do this for us since range(5, 3) == [] in python.

  return last_passing, first_failing


def reason_key_for_alert(alert):
  """Computes the reason key for an alert.

  The reason key for an alert is used to group related alerts together. Alerts
  for the same step name and reason are grouped together, and alerts for the
  same step name and builder are grouped together.
  """
  # FIXME: May need something smarter for reason_key.
  reason_key = alert['step_name']
  if alert['reason']:
    reason_key += ':%s' % alert['reason']
  else:
    # If we don't understand the alert, just make it builder-unique.
    reason_key += ':%s' % alert['builder_name']
  return reason_key


def group_by_reason(alerts):  # pragma: no cover
  by_reason = collections.defaultdict(list)
  for alert in alerts:
    by_reason[reason_key_for_alert(alert)].append(alert)

  reason_groups = []
  for reason_key, alerts in by_reason.items():
    last_passing, first_failing = merge_regression_ranges(alerts)
    blame_list = flatten_to_commit_list(last_passing, first_failing)
    # FIXME: blame_list isn't filtered yet, but should be.
    # FIXME: THIS IS A TEMPORARY HACK. WE SHOULD NOT TRUNCATE THIS LIST.
    # But it turns out that sometimes it thinks that it is reasonable to send
    # a blamelist 300,000 commits long, which just shouldn't happen.
    if len(blame_list) > 1000:
      logging.warn('Had to truncate blame list (%r:%r, length %s) for %s',
          last_passing, first_failing, len(blame_list), reason_key)

    blame_list = blame_list[-1000:]
    reason_groups.append({
        'sort_key': reason_key,
        'merged_last_passing': last_passing,
        'merged_first_failing': first_failing,
        'likely_revisions': blame_list,
        'failure_keys': map(operator.itemgetter('key'), alerts),
    })
  return reason_groups


def range_key_for_group(group):
  last_passing = group['merged_last_passing']
  first_failing = group['merged_first_failing']

  if last_passing:
    range_key = ' '.join(flatten_to_commit_list(last_passing, first_failing))
  elif first_failing:
    # Even regressions where we don't know when they started can be
    # merged by our earliest known failure.
    parts = ['<=%s:%s' % (name, commit)
             for name, commit in first_failing.items()]
    range_key = ' '.join(parts)
  else:
    range_key = 'no_first_failing'

  # sort_key is a heuristic to avoid merging failiures like
  # gclient revert + webkit_tests which just happened to pull
  # exact matching revisions when failing.
  return group['sort_key'][:3] + range_key


def merge_by_range(reason_groups):
  if not reason_groups:
    return []
  by_range = {}
  for group in reason_groups:
    range_key = range_key_for_group(group)
    existing = by_range.get(range_key)
    if not existing:
      # Shallow copy of group.
      by_range[range_key] = dict(group)
      continue

    # We only care about these two keys, the rest should be the same.
    # I guess we could assert that...
    sort_key = string_helpers.longest_substring(existing['sort_key'],
                                                group['sort_key'])
    failure_keys = sorted(set(existing['failure_keys'] + group['failure_keys']))
    by_range[range_key].update({
        'sort_key': sort_key,
        'failure_keys': failure_keys,
    })

  return sorted(by_range.values(), key=operator.itemgetter('sort_key'))
