# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from google.appengine.ext.webapp import template

from model.flake import Flake

import datetime
import logging
import time
import webapp2


MAX_GROUP_DISTANCE = datetime.timedelta(days=3)
MAX_OCCURRENCES_DEFAULT = 50
FLAKINESS_DASHBOARD_URL = (
  'http://test-results.appspot.com/dashboards/flakiness_dashboard.html#'
  'testType=%(normalized_step_name)s&tests=%(test_name)s')


def RunsSortFunction(s):  # pragma: no cover
  return s.time_finished

def filterNone(elements):
  return [e for e in elements if e is not None]

def _is_webkit_test_name(flake_name):
  if '/' not in flake_name:
    return False

  file_name = flake_name.split('/')[-1]
  return file_name.endswith(('.html', '.xml', '.xhtml', '.xht', '.pl', '.htm',
                             '.php', '.svg', '.mht', '.pdf',))

def show_all_flakes(flake, show_all):  # pragma: no cover
  from_index = 0 if show_all else -MAX_OCCURRENCES_DEFAULT
  occurrences = filterNone(ndb.get_multi(flake.occurrences[from_index:]))

  failure_runs_keys = []
  patchsets_keys = []
  flakes = []
  for o in occurrences:
    failure_runs_keys.append(o.failure_run)
    patchsets_keys.append(o.failure_run.parent())
    flakes.append(f for f in o.flakes if f.failure == flake.name)

  failure_runs = filterNone(ndb.get_multi(failure_runs_keys))
  patchsets = filterNone(ndb.get_multi(patchsets_keys))

  class FailureRunExtended:
    def __init__(self, url, patchset_url, builder, formatted_time, issue_ids,
                 time_finished):
      self.url = url
      self.patchset_url = patchset_url
      self.builder = builder
      self.formatted_time = formatted_time
      self.issue_ids = issue_ids
      self.time_finished = time_finished

  failure_runs_extended = []
  for index, fr in enumerate(failure_runs):
    failure_runs_extended.append(FailureRunExtended(
      fr.getURL(),
      patchsets[index].getURL(),
      patchsets[index].builder,
      fr.time_finished.strftime('%Y-%m-%d %H:%M:%S UTC'),
      set([f.issue_id for f in flakes[index] if f.issue_id > 0]),
      fr.time_finished,
    ))

  # Do simple sorting to make reading easier.
  failure_runs_extended = sorted(
      failure_runs_extended, key=RunsSortFunction, reverse=True)

  # Group flaky runs into periods separated by at least 3 days.
  grouped_runs = []
  if failure_runs_extended:
    current_group = [failure_runs_extended[0]]
    for f in failure_runs_extended[1:]:
      if current_group[-1].time_finished - f.time_finished < MAX_GROUP_DISTANCE:
        current_group.append(f)
      else:
        grouped_runs.append(current_group)
        current_group = [f]
    grouped_runs.append(current_group)

  show_all_link = (len(flake.occurrences) > MAX_OCCURRENCES_DEFAULT and
                   not show_all)
  values = {
    'flake': flake,
    'grouped_runs': grouped_runs,
    'show_all_link': show_all_link,
    'time_now': datetime.datetime.utcnow(),
  }

  # TODO(sergiyb): Currently we do not have information about which step a
  # given flaky test is executed in, see http://crbug.com/621454. However,
  # since flakiness is mostly found in webkit_tests, we can use a hard-coded
  # step name if we discover that test name looks like WebKit test. This should
  # change after we start recording step name for each test flake.
  if not flake.is_step and _is_webkit_test_name(flake.name):
    values['flakiness_dashboard_url'] = FLAKINESS_DASHBOARD_URL % {
      'normalized_step_name': 'webkit_tests (with patch)',
      'test_name': flake.name,
    }

  return template.render('templates/all_flake_occurrences.html', values)

class AllFlakeOccurrences(webapp2.RequestHandler):  # pragma: no cover
  def get(self):
    key = self.request.get('key').rstrip('.')
    flake = ndb.Key(urlsafe=key).get()
    show_all = self.request.get('show_all', 0)

    if not flake:
      self.response.set_status(404, 'Flake with id %s does not exist' % key)
      return

    self.response.write(show_all_flakes(flake, show_all))
