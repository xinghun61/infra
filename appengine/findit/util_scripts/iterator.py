# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches entities and iterate over and process them."""

import os

import remote_api  # pylint: disable=W

_DEFAULT_BATCH_SIZE = 1000


# TODO(katesonia): Move this to gae_libs.
# TODO(crbug.com/662540): Add unittests.
def Iterate(query,
            projection=None,
            batch_size=_DEFAULT_BATCH_SIZE,
            batch_run=False):  # pragma: no cover.
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


def ScriptIterate(query,
                  app_id,
                  projection=None,
                  batch_size=_DEFAULT_BATCH_SIZE,
                  batch_run=False):  # pragma: no cover.
  """Iterates entities queried by query.

  Args:
    query (ndb.Query): The query to fetch entities.
    batch_size (int): The number of entities to query at one time.
    batch_run (bool): If True, iterate batches of entities, if
      False, iterate each entity.

    An exmaple is available in crash_printer/print_crash.py.
  """
  remote_api.EnableRemoteApi(app_id)

  for entity in Iterate(query, projection=projection, batch_size=batch_size,
                        batch_run=batch_run):
    yield entity
