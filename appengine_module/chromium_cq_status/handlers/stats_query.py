# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.datastore.datastore_query import Cursor
import webapp2

from appengine_module.chromium_cq_status.shared.config import MAXIMUM_QUERY_SIZE
from appengine_module.chromium_cq_status.shared.parsing import (
  parse_cursor,
  parse_non_negative_integer,
  parse_request,
  parse_string,
  parse_strings,
  parse_timestamp,
  use_default,
)
from appengine_module.chromium_cq_status.shared.utils import compressed_json_dump  # pylint: disable=C0301
from appengine_module.chromium_cq_status.model.cq_stats import CQStats

def execute_query(project, interval_days, begin, end, names,
    count, cursor): # pragma: no cover
  count = min(count, MAXIMUM_QUERY_SIZE)

  stats_list = []
  next_cursor = ''
  more = True
  while more and len(stats_list) < count:
    filters = []
    if project:
      filters.append(CQStats.project == project)
    if interval_days:
      filters.append(CQStats.interval_days == interval_days)
    if begin:
      filters.append(CQStats.begin >= begin)
    if end:
      filters.append(CQStats.begin <= end)
    query = CQStats.query().filter(*filters).order(CQStats.begin)
    page_stats, next_cursor, more = query.fetch_page(count - len(stats_list),
        start_cursor=Cursor(urlsafe=next_cursor or cursor))
    next_cursor = next_cursor.urlsafe() if next_cursor else ''
    for stats in page_stats:
      if not names or stats.has_any_names(names):
        stats_list.append(stats)

  return {
    'results': [stats.to_dict(names) for stats in stats_list],
    'cursor': next_cursor,
    'more': more,
  }

class StatsQuery(webapp2.RequestHandler): # pragma: no cover
  def get(self): # pylint: disable-msg=W0221
    try:
      data = parse_request(self.request, {
        'project': parse_string,
        'interval_days': use_default(parse_non_negative_integer, None),
        'begin': parse_timestamp,
        'end': parse_timestamp,
        'names': parse_strings,
        'count': use_default(parse_non_negative_integer, 100),
        'cursor': parse_cursor,
      })
    except ValueError, e:
      self.response.write(e)
      return

    results = execute_query(**data)
    self.response.headers.add_header("Access-Control-Allow-Origin", "*")
    self.response.headers.add_header('Content-Type', 'application/json')
    compressed_json_dump(results, self.response)
