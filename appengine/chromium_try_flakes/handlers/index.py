# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import ndb
from google.appengine.ext.webapp import template

from model.flake import Flake
from status.cq_status import is_last_hour
from status.cq_status import is_last_day
from status.cq_status import is_last_week
from status.cq_status import is_last_month
from third_party.pytz.gae import pytz

import datetime
import logging
import time
import webapp2

def FlakeSortFunction(s):
  return s.builder + str(time.mktime(s.time_finished.timetuple()))

class Index(webapp2.RequestHandler):
  def get(self):
    range = self.request.get('range', default_value='day')
    cursor = Cursor(urlsafe=self.request.get('cursor'))
    flakes_query = Flake.query()
    if range == 'hour':
      flakes_query = flakes_query.filter(Flake.last_hour == True)
      flakes_query = flakes_query.order(-Flake.count_hour)
    elif range == 'day':
      flakes_query = flakes_query.filter(Flake.last_day == True)
      flakes_query = flakes_query.order(-Flake.count_day)
    elif range == 'week':
      flakes_query = flakes_query.filter(Flake.last_week == True)
      flakes_query = flakes_query.order(-Flake.count_week)
    elif range == 'month':
      flakes_query = flakes_query.filter(Flake.last_month == True)
      flakes_query = flakes_query.order(-Flake.count_month)
    else:
      flakes_query = flakes_query.order(-Flake.count_all)

    flakes_query = flakes_query.order(-Flake.last_time_seen)
    flakes, next_cursor, more = flakes_query.fetch_page(10, start_cursor=cursor)

    # Filter out occurrences so that we only show ones for the selected time
    # range. This is less confusing to read, and also less cluttered and renders
    # faster when not viewing all range.
    for f in flakes:
      # get_multi is much faster than calling .get for each f.occurrences
      occurrences = ndb.get_multi(f.occurrences)

      failure_run_keys = []
      patchsets_keys = []
      for o in occurrences:
        failure_run_keys.append(o.failure_run)
        patchsets_keys.append(o.failure_run.parent())

      failure_runs = ndb.get_multi(failure_run_keys)
      patchsets = ndb.get_multi(patchsets_keys)

      f.filtered_occurrences = []
      # tryserver pages show PST time so do so here as well for easy comparison.
      pst_timezone = pytz.timezone("US/Pacific")
      for index, r in enumerate(failure_runs):
        if (range == 'hour' and is_last_hour(r.time_finished)) or \
           (range == 'day' and is_last_day(r.time_finished)) or \
           (range == 'week' and is_last_week(r.time_finished)) or \
           (range == 'month' and is_last_month(r.time_finished)) or \
           range == 'all':
          r.patchset_url = patchsets[index].getURL()
          r.builder = patchsets[index].builder

          time_format = ''
          if range == 'hour':
            time_format = '%I:%M %p'
          elif range == 'day' or range == 'week' or range == 'month':
            time_format = '%m/%d %I:%M %p'
          else:
            time_format = '%m/%d/%y %I:%M %p'
          r.formatted_time = r.time_finished.replace(tzinfo=pytz.utc). \
              astimezone(pst_timezone).strftime(time_format)
          f.filtered_occurrences.append(r)

      # Do simple sorting of occurances by builder to make reading easier.
      f.filtered_occurrences = sorted(f.filtered_occurrences,
                                      key=FlakeSortFunction)

    values = {
      'range': range,
      'flakes': flakes,
      'more': more,
      'cursor': next_cursor.urlsafe() if next_cursor else '',
    }
    self.response.write(template.render('templates/index.html', values))
