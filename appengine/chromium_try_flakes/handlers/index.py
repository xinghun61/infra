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

import datetime
import logging
import time
import webapp2

def FlakeSortFunction(s):  # pragma: no cover
  return s.builder + str(time.mktime(s.time_finished.timetuple()))

def GetFilteredOccurences(flake, time_formatter,
                          filter_function):  # pragma: no cover
  occurrences = ndb.get_multi(flake.occurrences)

  failure_run_keys = []
  patchsets_keys = []
  for o in occurrences:
    failure_run_keys.append(o.failure_run)
    patchsets_keys.append(o.failure_run.parent())

  failure_runs = ndb.get_multi(failure_run_keys)
  patchsets = ndb.get_multi(patchsets_keys)

  filtered_occurrences = []
  for index, r in enumerate(failure_runs):
    if filter_function(r.time_finished):
      r.patchset_url = patchsets[index].getURL()
      r.builder = patchsets[index].builder
      r.formatted_time = time_formatter(r.time_finished)
      filtered_occurrences.append(r)

  # Do simple sorting of occurrences by builder to make reading easier.
  return sorted(filtered_occurrences, key=FlakeSortFunction)


class Index(webapp2.RequestHandler):  # pragma: no cover
  def get(self):
    time_range = self.request.get('range', default_value='day')
    cursor = Cursor(urlsafe=self.request.get('cursor'))
    flakes_query = Flake.query()
    if time_range == 'hour':
      flakes_query = flakes_query.filter(Flake.last_hour == True)
      flakes_query = flakes_query.order(-Flake.count_hour)
    elif time_range == 'day':
      flakes_query = flakes_query.filter(Flake.last_day == True)
      flakes_query = flakes_query.order(-Flake.count_day)
    elif time_range == 'week':
      flakes_query = flakes_query.filter(Flake.last_week == True)
      flakes_query = flakes_query.order(-Flake.count_week)
    elif time_range == 'month':
      flakes_query = flakes_query.filter(Flake.last_month == True)
      flakes_query = flakes_query.order(-Flake.count_month)
    else:
      flakes_query = flakes_query.order(-Flake.count_all)

    flakes_query = flakes_query.order(-Flake.last_time_seen)
    flakes, next_cursor, more = flakes_query.fetch_page(10, start_cursor=cursor)

    # Filter out occurrences so that we only show ones for the selected time
    # range. This is less confusing to read, and also less cluttered and renders
    # faster when not viewing all range.
    def filter_by_range(t):
      if time_range == 'hour':
        return is_last_hour(t)
      if time_range == 'day':
        return is_last_day(t)
      if time_range == 'week':
        return is_last_week(t)
      if time_range == 'month':
        return is_last_month(t)
      if time_range == 'all':
        return True

    time_format = ''
    if time_range == 'hour':
      time_format = '%H:%M:%S'
    else:
      time_format = '%Y-%m-%d %H:%M:%S'

    def time_formatter(t):
      return t.strftime(time_format)

    for f in flakes:
      f.filtered_occurrences = GetFilteredOccurences(
          f, time_formatter, filter_by_range)

    values = {
      'range': time_range,
      'flakes': flakes,
      'more': more,
      'cursor': next_cursor.urlsafe() if next_cursor else '',
    }
    self.response.write(template.render('templates/index.html', values))
