# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import time
from datetime import timedelta

from google.appengine.datastore.datastore_query import Cursor

from libs import time_util

DATE_FORMAT = '%Y-%m-%d'

PAGE_SIZE = 100
PREVIOUS = 'previous'
NEXT = 'next'

# Order type of a property in forwarding paging.
ASC = 'asc'
DESC = 'desc'


def GetStartAndEndDates(start_date=None, end_date=None):
  """Gets start_date and end_date datetime objects.

  Returns by default midnight yesterday as start_date and midnight_tomorrow as
  end_date if not specified.
  """
  midnight_today = datetime.combine(time_util.GetUTCNow(), time.min)
  midnight_yesterday = midnight_today - timedelta(days=1)
  midnight_tomorrow = midnight_today + timedelta(days=1)

  start_date = (
      datetime.strptime(start_date, DATE_FORMAT)
      if start_date else midnight_yesterday)
  end_date = (
      datetime.strptime(end_date, DATE_FORMAT)
      if end_date else midnight_tomorrow)

  return start_date, end_date


def GetPagedResults(query,
                    order_properties,
                    cursor=None,
                    direction=NEXT,
                    page_size=PAGE_SIZE):
  """Paging the query results with page_size.

  Args:
    query(ndb.Query): The ndb query to query entities.
    order_properties: A list of tuples containing class attribute of entity
      class to order the entities and ordering of the field.
    cursor (Cursor): The cursor provides a cursor in the current query
      results, allowing you to retrieve the next set based on the offset.
    direction (str): Either previous or next.
    page_size (int): Number of entities to show per page.

  Returns:
    A tuple of (entities, top_cursor, next_cursor).
    entities (list): List of entities to be displayed at the current page.
    top_cursor (str): The urlsafe encoding of the cursor, which is at the
      top position of entities of the current page.
    bottom_cursor (str): The urlsafe encoding of the cursor, which is at the
      bottom position of entities of the current page.
  """
  cursor = Cursor(urlsafe=cursor) if cursor else None

  if direction.lower() == PREVIOUS:
    for order_property, forward_order in order_properties:
      if forward_order == DESC:
        # Forward order is desc meaning backward order should be asc.
        query = query.order(order_property)
      if forward_order == ASC:
        # Forward order is asc meaning backward order should be desc.
        query = query.order(-order_property)
    entities, next_cursor, more = query.fetch_page(
        page_size, start_cursor=cursor.reversed())
    entities.reverse()
  else:
    for order_property, forward_order in order_properties:
      if forward_order == DESC:
        query = query.order(-order_property)
      if forward_order == ASC:
        query = query.order(order_property)
    entities, next_cursor, more = query.fetch_page(
        page_size, start_cursor=cursor)

  next_cursor = next_cursor.urlsafe() if next_cursor else ''
  used_cursor = cursor.urlsafe() if cursor else ''
  if direction.lower() == PREVIOUS:
    top_cursor = next_cursor if more else ''
    bottom_cursor = used_cursor
  else:
    top_cursor = used_cursor
    bottom_cursor = next_cursor if more else ''

  return entities, top_cursor, bottom_cursor
