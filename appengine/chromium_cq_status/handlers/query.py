# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import calendar

from google.appengine.datastore.datastore_query import Cursor
import webapp2

from shared.config import MAXIMUM_QUERY_SIZE
from shared.parsing import (
  parse_cursor,
  parse_url_tags,
  parse_fields,
  parse_key,
  parse_non_negative_integer,
  parse_request,
  parse_tags,
  parse_timestamp,
  use_default,
)
from model.record import Record # pylint: disable-msg=E0611

def execute_query(
    key, begin, end, tags, fields, count, cursor): # pragma: no cover
  count = min(count, MAXIMUM_QUERY_SIZE)

  filters = []
  if begin:
    filters.append(Record.timestamp >= begin)
  if end:
    filters.append(Record.timestamp <= end)
  for tag in tags:
    filters.append(Record.tags == tag)

  results = []
  more = True
  next_cursor = ''
  while more and len(results) < count:
    if key and not filters and count > 0:
      record = Record.get_by_id(key)
      records = [record] if record else []
      more = False
    else:
      query = Record.query().filter(*filters).order(-Record.timestamp)
      records, next_cursor, more = query.fetch_page(count - len(results),
          start_cursor=Cursor(urlsafe=cursor))
      next_cursor = next_cursor.urlsafe() if next_cursor else ''

    for record in records:
      for field, value in fields.items():
        if not field in record.fields or record.fields[field] != value:
          break
      else:
        result = record.to_dict(exclude=['timestamp'])
        result['timestamp'] = calendar.timegm(record.timestamp.timetuple())
        record_key = record.key.id()
        result['key'] = record_key if type(record_key) != long else None
        results.append(result)
  return {
    'results': results,
    'cursor': next_cursor,
    'more': more,
  }

class Query(webapp2.RequestHandler): # pragma: no cover
  def get(self, url_tags): # pylint: disable-msg=W0221
    try:
      data = parse_request(self.request, {
        'begin': parse_timestamp,
        'end': parse_timestamp,
        'key': parse_key,
        'tags': parse_tags,
        'fields': parse_fields,
        'count': use_default(parse_non_negative_integer, 100),
        'cursor': parse_cursor,
      })
      data['tags'].extend(parse_url_tags(url_tags))
    except ValueError, e:
      self.response.write(e)
      return

    results = execute_query(**data)
    self.response.headers.add_header('Content-Type', 'application/json')
    json.dump(results, self.response)
