# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict, namedtuple
import datetime
import logging
import urllib2
import webapp2

from google.appengine.ext import ndb

from common import data_interface, monorail_interface
from model.flake import FlakeType, Issue, FlakeUpdate, FlakeUpdateSingleton
from handlers.update_issues import update_issue_ids


MAX_UPDATES_PER_DAY = 10


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


def _get_project_key(project):
  project_key = ndb.Key('FlakeUpdateSingleton', project)
  if not project_key.get():
    FlakeUpdateSingleton(key=project_key).put()
  return project_key


def _project_has_no_updates_left(project):
  project_key = _get_project_key(project)
  yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
  return FlakeUpdate.query(FlakeUpdate.time_updated > yesterday,
                           ancestor=project_key).count() >= MAX_UPDATES_PER_DAY


def _add_update_for_project(project):
  project_key = _get_project_key(project)
  FlakeUpdate(parent=project_key).put()


def _get_updates_and_new_flakes(flakes_data):
  query_futures = []
  new_flakes_by_project = defaultdict(list)

  flakes_data_items = sorted(flakes_data.items())
  for (project, step_name, test_name, config), flakes in flakes_data_items:
    if _project_has_no_updates_left(project):
      continue

    flake_types = FlakeType.query(FlakeType.project == project,
                                  FlakeType.step_name == step_name,
                                  FlakeType.test_name == test_name,
                                  FlakeType.config == config).fetch(1)

    last_updated = max(_get_flake_timestamp(flake) for flake in flakes)

    if flake_types:
      flake_type = flake_types[0]
      flakes_count = _count_flakes_since_last_update(
          flakes, flake_type.last_updated)
      if not flakes_count:
        continue
      flake_info = FlakeInfo(flake_type=flake_type, flakes_count=flakes_count)
      query_future = Issue.query(
          Issue.flake_type_keys == flake_type.key).fetch_async()
      query_futures.append((query_future, flake_info, last_updated))
    else:
      flakes_count = len(flakes)
      flake_type = FlakeType(project=project, step_name=step_name,
                             test_name=test_name, config=config,
                             last_updated=last_updated)
      flake_type.put()
      flake_info = FlakeInfo(flake_type=flake_type, flakes_count=flakes_count)
      new_flakes_by_project[project].append(flake_info)

  # We create a single Issue for all new FlakeTypes of a given project, hence a
  # single update needs to be added.
  for project in new_flakes_by_project:
    _add_update_for_project(project)

  new_flakes_by_issue = defaultdict(list)
  for query_future, flake_info, last_updated in query_futures:
    for issue in query_future.get_result():
      if issue.key not in new_flakes_by_issue:
        # We count each Issue only once when we first see it (i.e here), since
        # all the FlakeType updates for a single Issue will be reported in a
        # single comment.
        if _project_has_no_updates_left(issue.project):
          continue
        _add_update_for_project(project)
      new_flakes_by_issue[issue.key].append(flake_info)
      # We wait until here to update the FlakeType entity's last_updated_field,
      # since we don't want to mark new flakes as updated if the project had no
      # updates left.
      flake_info.flake_type.last_updated = last_updated
      flake_info.flake_type.put()

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
