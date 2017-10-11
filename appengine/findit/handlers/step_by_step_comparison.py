# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Given two tryjob urls, compare their executions."""

from collections import namedtuple
import json

from common.findit_http_client import FinditHttpClient
from common import rpc_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util

from waterfall import buildbot


def _Flatten(build_info):
  """Recursively flatten nested steps lists."""
  steps = []
  if 'name' in build_info['step']:
    steps.append(build_info['step'])
  for step in build_info['step'].get('substep', []):
    inner_steps = _Flatten(step)
    steps += inner_steps
  return steps


def _GetStepNames(steps):
  return set([step['name'] for step in steps if 'name' in step])


def _GetStepsForTryJob(url, http_client):
  if not buildbot.ValidateBuildUrl(url):
    raise ValueError('Invalid Url')
  build_info = json.loads(buildbot.GetBuildInfo(url, http_client))
  return _Flatten(build_info)


def _FindByName(label, steps):
  for s in steps:
    if s.get('name') == label:
      return s


class _ComparisonTable(object):

  def __init__(self, left_steps, right_steps):
    self.left_steps = left_steps
    self.right_steps = right_steps
    self.left_labels = _GetStepNames(left_steps)
    self.right_labels = _GetStepNames(right_steps)
    self.common_labels = self.left_labels & self.right_labels
    self.result_left = []
    self.result_right = []

  def _MoveTopsToResult(self, left, right):
    self.result_left.append((left or [None]).pop(0))
    self.result_right.append((right or [None]).pop(0))

  def _LocateMatchAndMoveToResult(self, label):
    matching_step = _FindByName(label, self.right_steps)
    self.right_steps.remove(matching_step)
    self._MoveTopsToResult(self.left_steps, [matching_step])

  def _MoveRemainingStepsToResult(self):
    while self.left_steps:
      self._MoveTopsToResult(self.left_steps, None)
    while self.right_steps:
      self._MoveTopsToResult(None, self.right_steps)

  def ArrangeSteps(self):
    while self.left_steps and self.right_steps:
      left_step_name = self.left_steps[0].get('name')
      right_step_name = self.right_steps[0].get('name')
      if left_step_name == right_step_name:
        self._MoveTopsToResult(self.left_steps, self.right_steps)
      elif left_step_name not in self.common_labels:
        self._MoveTopsToResult(self.left_steps, None)
      elif right_step_name not in self.common_labels:
        self._MoveTopsToResult(None, self.right_steps)
      else:
        self._LocateMatchAndMoveToResult(left_step_name)
    self._MoveRemainingStepsToResult()
    return [self.result_left, self.result_right]


def _ParseTime(t):
  """Thin wrapper around time_util's implementation of string date parsing

  The purpose of this wrapper is to truncate the nanoseconts and the Z suffix
  off of the parameter, as nanoseconds are too fine-grained for our purposes and
  the time zone is unnecessary as we deal with time deltas.
  """
  # Discard nanosecond data and Zulu time suffix.
  seconds, sub_second = t.split('.')
  t = '.'.join([seconds, sub_second[:6]])
  return time_util.DatetimeFromString(t)


def _ComputeElapsedTime(step):
  if step and 'ended' in step and 'started' in step:
    return (_ParseTime(step.get('ended')) -
            _ParseTime(step.get('started'))).total_seconds()
  return 0


def _MakeRow(left, right):
  """Prepare a row for display from two matching steps.

  Given two steps, compute their elapsed time and relative time difference and
  arrange this data in a list for tabular display.
  """
  _DisplayRow = namedtuple('_DisplayRow', [
      'left_name', 'left_time', 'right_name', 'right_time', 'time_diff'
  ])

  left = left or {}
  right = right or {}
  left_time = _ComputeElapsedTime(left)
  right_time = _ComputeElapsedTime(right)
  return _DisplayRow(
      left.get('name'), left_time,
      right.get('name'), right_time, right_time - left_time)


class _ComparisonStats(object):

  def __init__(self, steps_table):
    self.rows = []

    # Accumulators for step duration sums.
    self.common_left = 0
    self.common_right = 0
    self.only_left = 0
    self.only_right = 0

    # Counters for number of steps.
    self.common_steps = 0
    self.left_only_steps = 0
    self.right_only_steps = 0
    self._ComputeStats(steps_table)

  def _ComputeStats(self, steps_table):
    for i in range(len(steps_table[0])):
      row = _MakeRow(steps_table[0][i], steps_table[1][i])
      self.rows.append(row)
      if row.left_time and row.right_time:
        self.common_left += row.left_time
        self.common_right += row.right_time
        self.common_steps += 1
      elif row.right_time:
        self.only_right += row.right_time
        self.right_only_steps += 1
      else:
        self.only_left += row.left_time
        self.left_only_steps = 1


class StepByStepComparison(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    http_client = FinditHttpClient()
    left_url = self.request.get('swarmbucket_try_job')
    right_url = self.request.get('buildbot_try_job')
    if not left_url or not right_url:
      return self.CreateError(
          'Both swarmbucket_try_job and buildbot_try_job parameters are '
          'required', 400)
    try:
      left_steps = _GetStepsForTryJob(left_url, http_client)
      right_steps = _GetStepsForTryJob(right_url, http_client)
    except ValueError:
      return self.CreateError(
          'At least one of the URLs in the request does not belong to a valid'
          ' tryjob', 400)

    steps_table = _ComparisonTable(left_steps, right_steps).ArrangeSteps()
    stats = _ComparisonStats(steps_table)

    return {
        'data': {
            'left_url': left_url,
            'right_url': right_url,
            'rows': stats.rows,
            'common_left_sum': stats.common_left,
            'common_right_sum': stats.common_right,
            'common_steps_count': stats.common_steps,
            'only_left_sum': stats.only_left,
            'only_right_sum': stats.only_right,
            'only_left_count': stats.left_only_steps,
            'only_right_count': stats.right_only_steps,
        }
    }
