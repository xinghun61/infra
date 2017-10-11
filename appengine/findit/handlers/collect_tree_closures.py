# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This handler is to collect tree closures. It runs in a cron job."""

from datetime import timedelta
import json
import logging
import re

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model.tree_closure import TreeClosure
from model.tree_closure import TreeStatus
from waterfall import buildbot

_MONITORED_TREES = {
    'chromium': 'https://chromium-status.appspot.com/allstatus',
}

_DEFAULT_BACKLOG_DAYS = 90  # For first run, check the last 90 days.

_AUTO_CLOSE_MESSAGE_PATTERN = re.compile(
    r'^Tree is closed \(Automatic: "(?P<step>[^"]+)" on '
    r'(?P<build>[^"]+) "(?P<builder>[^"]+)" from .*$')


def _GetCurrentCheckingPointForTree(tree_name):
  """Returns the timestamp from which to start the current checking."""
  query = TreeClosure.query(
      TreeClosure.tree_name == tree_name).order(-TreeClosure.closed_time)
  result = query.get()
  if result:
    return result.opened_time

  now = time_util.GetUTCNow()
  return now - timedelta(days=_DEFAULT_BACKLOG_DAYS)


def _CreateTreeStatus(tree_status_entry):
  """Creates a TreeStatus model based on the given json data."""
  return TreeStatus(
      time=time_util.DatetimeFromString(tree_status_entry['date']),
      message=tree_status_entry['message'],
      state=tree_status_entry['general_state'],
      username=tree_status_entry['username'],)


def _RetrieveTreeStatus(tree_name, start_time, end_time=None):
  """Returns a time-ascending-sorted TreeStatus list since checking point."""
  url = _MONITORED_TREES[tree_name]
  params = {
      'limit': 1000,  # 1000 is large enough to get all recent tree statuses.
      'format': 'json',
      # Tree status app treats endTime as the beginning of the time range.
      'endTime': time_util.ConvertToTimestamp(start_time),
  }
  if end_time:
    # Tree status app treats startTime as the end of the time range.
    params['startTime'] = time_util.ConvertToTimestamp(end_time)
  http_client = FinditHttpClient()
  status_code, content = http_client.Get(url, params=params)
  if status_code == 200:
    all_statuses = map(_CreateTreeStatus, json.loads(content))
    all_statuses.sort(key=lambda s: s.time)
    # With 'endTime' set, the Tree status app always includes a duplicate entry
    # for the latest status.
    return all_statuses[:-1]
  else:
    logging.error('Failed to retrieve tree status for %s from %r to %r',
                  tree_name, start_time, end_time)
    return []  # Wait for next execution.


def _ExtractFailureInfo(message):
  """Returns the master/builder/build id/step name of the failure."""
  master_name = None
  builder_name = None
  build_id = None
  step_name = None

  match = _AUTO_CLOSE_MESSAGE_PATTERN.match(message)
  if match:
    step_name = match.group('step')
    builder_name = match.group('builder')
    build = match.group('build')
    build_info = buildbot.ParseBuildUrl(build)
    if build_info:
      master_name = build_info[0]
      build_id = str(build_info[-1])
    else:
      build_id = build.split('/')[-1]

  return (master_name, builder_name, build_id, step_name)


def _CreateTreeClosure(tree_name, statuses, first_open_status):
  """Creates a TreeClosure based on the given statuses."""
  closed_time = statuses[0].time
  opened_time = first_open_status.time
  latest_action_time = statuses[-1].time

  auto_closed = statuses[0].automatic
  auto_opened = first_open_status.automatic

  possible_flake = False
  has_revert = False
  for s in statuses[1:]:
    message = s.message.lower()
    for signal in ('flake', 'flaky', 'bot failure'):
      if signal in message:
        possible_flake = True
    if 'revert' in message:
      has_revert = True

  master_name, builder_name, build_id, step_name = _ExtractFailureInfo(
      statuses[0].message)

  key_str_id = '%s-%s' % (tree_name, time_util.ConvertToTimestamp(closed_time))

  return TreeClosure(
      tree_name=tree_name,
      statuses=statuses,
      closed_time=closed_time,
      opened_time=opened_time,
      latest_action_time=latest_action_time,
      auto_closed=auto_closed,
      auto_opened=auto_opened,
      possible_flake=possible_flake,
      has_revert=has_revert,
      master_name=master_name,
      builder_name=builder_name,
      build_id=build_id,
      step_name=step_name,
      key=ndb.Key(TreeClosure, key_str_id),)


def _DetectTreeClosureForTree(tree_name, all_statuses):
  """Detects tree closures for the given tree, and return the number."""
  tree_closures = []
  index = 0

  previous_closure_complete = False
  while index < len(all_statuses):
    # Skip all leading open statuses to find the next closure.
    if not all_statuses[index].closed:
      index += 1
      continue

    close_index = index
    index += 1

    first_open_index = None
    # Skip all non-open status (close, throttle) to find the next open status.
    while index < len(all_statuses):
      if not all_statuses[index].closed:
        first_open_index = index
        break
      index += 1

    latest_open_index = first_open_index
    # Skip to the most recent open status for this tree closure.
    while index < len(all_statuses):
      if all_statuses[index].closed:
        break
      latest_open_index = index
      index += 1

    # Skip if no matching open status is found.
    if first_open_index is not None:
      # The identified closure might not be complete with all the open statuses.
      tree_closures.append(
          _CreateTreeClosure(tree_name, all_statuses[
              close_index:latest_open_index + 1], all_statuses[
                  first_open_index]))
    else:
      # The previous tree closure was complete with all the open statuses,
      # because a new tree closure started and was incomplete.
      previous_closure_complete = True

  if not previous_closure_complete:
    tree_closures = tree_closures[:-1]
  # Save all the closures to datastore.
  return len(ndb.put_multi(tree_closures))


class CollectTreeClosures(BaseHandler):
  """Checks and records tree closures since last checking."""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    start_time = time_util.DatetimeFromString(
        self.request.get('start_time', None))
    end_time = time_util.DatetimeFromString(self.request.get('end_time', None))
    closure_counts = {}
    for tree_name in _MONITORED_TREES:
      start_time = start_time or _GetCurrentCheckingPointForTree(tree_name)
      all_statuses = _RetrieveTreeStatus(
          tree_name, start_time, end_time=end_time)
      closure_counts[tree_name] = _DetectTreeClosureForTree(
          tree_name, all_statuses)
    return {'data': closure_counts}
