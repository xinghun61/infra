# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches entities and iterate over and process them."""

from gae_libs import iterator
from local_libs import remote_api  # pylint: disable=W


def ScriptIterate(query,
                  app_id,
                  projection=None,
                  batch_size=iterator.DEFAULT_BATCH_SIZE,
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

  for entity in iterator.Iterate(query, projection=projection,
                                 batch_size=batch_size,
                                 batch_run=batch_run):
    yield entity
