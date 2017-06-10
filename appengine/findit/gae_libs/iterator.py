# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches entities and iterate over and process them."""

DEFAULT_BATCH_SIZE = 1000


def Iterate(query,
            projection=None,
            batch_size=DEFAULT_BATCH_SIZE,
            batch_run=False):
  """Iterates entities queried by query.

  Args:
    query (ndb.Query): The query to fetch entities.
    projection (tuple or list): Operations return entities with only the
      specified properties set. For example:
      projection=[Article.title, Article.date] or
      projection=['title', 'date'] fetches entities with just those two
      fields set. Note, query can only project indexed properties.
    batch_size (int): The number of entities to query at one time.
    batch_run (bool): If True, iterate batches of entities, if
      False, iterate each entity.

    An exmaple is available in crash_printer/print_crash.py.
  """
  cursor = None
  while True:
    entities, next_cursor, more = query.fetch_page(batch_size,
                                                   projection=projection,
                                                   start_cursor=cursor)
    if not more and not entities:
      break

    if batch_run:
      yield entities
    else:
      for entity in entities:
        yield entity

    if not more:
      break

    cursor = next_cursor
