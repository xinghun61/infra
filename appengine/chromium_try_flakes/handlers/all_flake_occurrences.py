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


def RunsSortFunction(s):  # pragma: no cover
  return s.time_finished

def show_all_flakes(flake, bug_friendly):  # pragma: no cover
  occurrence_keys = []
  for o in flake.occurrences:
    occurrence_keys.append(o)

  occurrences = ndb.get_multi(occurrence_keys)

  failure_runs_keys = []
  patchsets_keys = []
  for o in occurrences:
    failure_runs_keys.append(o.failure_run)
    patchsets_keys.append(o.failure_run.parent())

  failure_runs = ndb.get_multi(failure_runs_keys)
  patchsets = ndb.get_multi(patchsets_keys)

  for index, f in enumerate(failure_runs):
    f.patchset_url = patchsets[index].getURL()
    f.builder = patchsets[index].builder
    f.formatted_time = f.time_finished.strftime('%Y-%m-%d %H:%M:%S UTC')

  # Do simple sorting to make reading easier.
  failure_runs = sorted(failure_runs, key=RunsSortFunction, reverse=True)

  grouped_runs = []
  if failure_runs:
    current_group = [failure_runs[0]]
    for f in failure_runs[1:]:
      if current_group[-1].time_finished - f.time_finished < MAX_GROUP_DISTANCE:
        current_group.append(f)
      else:
        grouped_runs.append(current_group)
        current_group = [f]
    grouped_runs.append(current_group)

  values = {
    'flake': flake,
    'grouped_runs': grouped_runs,
    'bug_friendly': bug_friendly,
    'time_now': datetime.datetime.utcnow(),
  }

  return template.render('templates/all_flake_occurrences.html', values)

class AllFlakeOccurrences(webapp2.RequestHandler):  # pragma: no cover
  def get(self):
    key = self.request.get('key')
    flake = ndb.Key(urlsafe=key).get()
    bug_friendly = self.request.get('bug_friendly', 0)

    self.response.write(show_all_flakes(flake, bug_friendly))
