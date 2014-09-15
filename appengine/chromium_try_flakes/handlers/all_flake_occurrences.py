# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from google.appengine.ext.webapp import template

from model.flake import Flake
from third_party.pytz.gae import pytz

import datetime
import logging
import time
import webapp2

def RunsSortFunction(s):
  return s.builder + str(time.mktime(s.time_finished.timetuple()))

def show_all_flakes(flake, bug_friendly):
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

  pst_timezone = pytz.timezone("US/Pacific")
  for index, f in enumerate(failure_runs):
    f.patchset_url = patchsets[index].getURL()
    f.builder = patchsets[index].builder
    f.formatted_time = f.time_finished.replace(tzinfo=pytz.utc).astimezone(
        pst_timezone).strftime('%m/%d/%y %I:%M %p')

  # Do simple sorting to make reading easier.
  failure_runs = sorted(failure_runs, key=RunsSortFunction)

  values = {
    'flake': flake,
    'failure_runs': failure_runs,
    'bug_friendly': bug_friendly,
    'time_now': datetime.datetime.now(),
  }

  return template.render('templates/all_flake_occurrences.html', values)

class AllFlakeOccurrences(webapp2.RequestHandler):
  def get(self):
    key = self.request.get('key')
    flake = ndb.Key(urlsafe=key).get()
    bug_friendly = self.request.get('bug_friendly', 0)

    self.response.write(show_all_flakes(flake, bug_friendly))
