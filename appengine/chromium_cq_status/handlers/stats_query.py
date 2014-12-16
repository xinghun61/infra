# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.datastore.datastore_query import Cursor
import webapp2

from model.cq_stats import CQStats
from shared.config import (
  LAST_CQ_STATS_INTERVAL_CHANGE_KEY,
  LAST_CQ_STATS_CHANGE_KEY,
)
from shared.parsing import (
  parse_cqstats_key,
  parse_cursor,
  parse_non_negative_integer,
  parse_query_count,
  parse_request,
  parse_string,
  parse_strings,
  parse_timestamp,
  use_default,
)
from shared import utils

from google.appengine.api import memcache

def check_last_change(cache_timestamp, kwargs): # pragma: no cover
  last_change_key = get_last_change_key(kwargs.get('interval_minutes'))
  last_change_timestamp = memcache.get(last_change_key)
  if last_change_timestamp is None:
    return False
  return cache_timestamp >= last_change_timestamp

def get_last_change_key(interval_minutes): # pragma: no cover
  if interval_minutes:
    return LAST_CQ_STATS_INTERVAL_CHANGE_KEY % interval_minutes
  return LAST_CQ_STATS_CHANGE_KEY

def ensure_last_change_timestamp(interval_minutes): # pragma: no cover
  """Ensure a memcache timestamp is set for the last CQStats change."""
  last_change_key = get_last_change_key(interval_minutes)
  last_change_timestamp = memcache.get(last_change_key)
  if last_change_timestamp is None:
    memcache.set(last_change_key, utils.timestamp_now())

@utils.memcachize(cache_check=check_last_change)
def execute_query(key, project, interval_minutes, begin, end, names,
    count, cursor): # pragma: no cover
  stats_list = []
  next_cursor = ''
  if key and count > 0:
    stats = CQStats.get_by_id(key)
    if stats and (
        (not project or stats.project == project) and
        (not interval_minutes or stats.interval_minutes == interval_minutes) and
        (not begin or stats.begin >= begin) and
        (not end or stats.end <= end) and
        (not names or stats.has_any_names(names))):
      stats_list.append(stats)
    more = False
  else:
    more = True
    while more and len(stats_list) < count:
      filters = []
      if project:
        filters.append(CQStats.project == project)
      if interval_minutes:
        filters.append(CQStats.interval_minutes == interval_minutes)
      if begin:
        filters.append(CQStats.begin >= begin)
      if end:
        filters.append(CQStats.begin <= end)
      query = CQStats.query().filter(*filters).order(-CQStats.begin)
      page_stats, next_cursor, more = query.fetch_page(count - len(stats_list),
          start_cursor=Cursor(urlsafe=next_cursor or cursor))
      next_cursor = next_cursor.urlsafe() if next_cursor else ''
      for stats in page_stats:
        if not names or stats.has_any_names(names):
          stats_list.append(stats)

  ensure_last_change_timestamp(interval_minutes)

  return {
    'results': [stats.to_dict(names) for stats in stats_list],
    'cursor': next_cursor,
    'more': more,
  }

class StatsQuery(webapp2.RequestHandler): # pragma: no cover
  @utils.cross_origin_json
  def get(self):
    try:
      params = parse_request(self.request, {
        'key': parse_cqstats_key,
        'project': parse_string,
        'interval_minutes': use_default(parse_non_negative_integer, None),
        'begin': parse_timestamp,
        'end': parse_timestamp,
        'names': parse_strings,
        'count': parse_query_count,
        'cursor': parse_cursor,
      })
      return execute_query(**params)
    except ValueError, e:
      self.response.write(e)
