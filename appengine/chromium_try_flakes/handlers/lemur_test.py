# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict, namedtuple
import datetime
import logging
import urllib2
import webapp2

from common import data_interface, monorail_interface
from model.flake import FlakeType, Issue
from handlers.update_issues import update_issue_ids


class FlakeInfo(object):
  def __init__(self, flake_type, flakes_count):
    self.flake_type = flake_type
    self.flakes_count = flakes_count

  def __lt__(self, other):
    self_tuple = (self.flake_type.project,
                  self.flake_type.step_name,
                  self.flake_type.test_name,
                  self.flake_type.config)

    other_tuple = (other.flake_type.project,
                   other.flake_type.step_name,
                   other.flake_type.test_name,
                   other.flake_type.config)

    return self_tuple < other_tuple

def _get_flake_timestamp(flake):
  return datetime.datetime.utcfromtimestamp(float(flake[0]) / 1000)


def _count_flakes_since_last_update(flakes_list, last_update):
  flakes_count = 0
  for flake in flakes_list:
    failure_time = _get_flake_timestamp(flake)
    if failure_time > last_update:
      flakes_count += 1

  return flakes_count


def _get_updates_and_new_flakes(flakes_data):
  query_futures = []
  new_flakes_by_project = defaultdict(list)
  for (project, step_name, test_name, config), flakes in flakes_data.items():
    flake_types = FlakeType.query(FlakeType.project == project,
                                  FlakeType.step_name == step_name,
                                  FlakeType.test_name == test_name,
                                  FlakeType.config == config).fetch(1)

    if flake_types:
      flake_type = flake_types[0]
      flakes_count = _count_flakes_since_last_update(
          flakes, flake_type.last_updated)
      if not flakes_count:
        continue
      flake_info = FlakeInfo(flake_type=flake_type, flakes_count=flakes_count)
      query_future = Issue.query(
          Issue.flake_type_keys == flake_type.key).fetch_async()
      query_futures.append((query_future, flake_info))
    else:
      flakes_count = len(flakes)
      flake_type = FlakeType(project=project, step_name=step_name,
                             test_name=test_name, config=config,
                             last_updated=datetime.datetime.min)
      flake_info = FlakeInfo(flake_type=flake_type, flakes_count=flakes_count)
      new_flakes_by_project[flake_type.project].append(flake_info)

    flake_type.last_updated = max(
        _get_flake_timestamp(flake) for flake in flakes)
    flake_type.put()

  new_flakes_by_issue = defaultdict(list)
  for query_future, flake_info in query_futures:
    for issue in query_future.get_result():
      new_flakes_by_issue[issue.key].append(flake_info)

  return new_flakes_by_project, new_flakes_by_issue


def _create_issue(project, new_flakes):
  issue_id = monorail_interface.create_issue(project, new_flakes)
  flake_type_keys = [flake_info.flake_type.key for flake_info in new_flakes]
  issue = Issue(project=project, issue_id=issue_id,
                flake_type_keys=flake_type_keys)
  issue.put()


def process_new_flakes():
  flakes_data = data_interface.get_flakes_data()
  new_flakes_by_project, new_flakes_by_issue = (
      _get_updates_and_new_flakes(flakes_data))

  new_flakes_by_issue = update_issue_ids(new_flakes_by_issue)

  for issue_key, new_flakes in new_flakes_by_issue.items():
    issue = issue_key.get()
    monorail_interface.update_issue(issue.project, issue.issue_id,
                                    sorted(new_flakes))

  for project, new_flakes in new_flakes_by_project.items():
    _create_issue(project, sorted(new_flakes))


class ProcessNewFlakes(webapp2.RequestHandler):
  def get(self):
    data_interface.update_cache()
    process_new_flakes()
    self.response.write("SUCCESS!")

# TODO(ehmaldonado): Remove.
# For testing.
class OnlyUpdateCache(webapp2.RequestHandler):  # pragma: no cover
  def get(self):
    data_interface.update_cache()
    self.response.write("SUCCESS!")

class OnlyProcessFlakes(webapp2.RequestHandler):  # pragma: no cover
  def get(self):
    process_new_flakes()
    self.response.write("SUCCESS!")
