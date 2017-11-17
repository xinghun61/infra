# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import threading
import time


class BigQueryHelper(object):
  """BigQueryHelper is a thread safe helper for some common BigQuery tasks."""

  def __init__(self, bq_client):
    """bq_client: an instance of google.cloud.bigquery.client.Client"""
    self._bq_client = bq_client
    self._lock = threading.RLock()

  def send_rows(self, dataset_id, table_id, rows):
    """
      rows: list of tuples, one tuple per row. Each tuple should contain data of
        the correct type for each schema field on the current table and in the
        same order as the schema fields.
    """
    with self._lock:
      table = self._bq_client.get_table(
        self._bq_client.dataset(dataset_id).table(table_id))
      insert_errors = self._bq_client.create_rows(table, rows)
    if insert_errors:
      logging.error('Failed to send event to bigquery: %s', insert_errors)
      raise BigQueryInsertError(insert_errors)


class BigQueryInsertError(Exception):
  """Error from create_rows() call on BigQuery client.

  insert_errors is in the form of a list of mappings, where each mapping
  contains an "index" key corresponding to a row and an "errors" key.
  """
  def __init__(self, insert_errors):
    message = self._construct_message(insert_errors)
    super(BigQueryInsertError, self).__init__(message)

  @staticmethod
  def _construct_message(insert_errors):
    message = ''
    for row_mapping in insert_errors:
      index = row_mapping.get('index')
      for err in row_mapping.get('errors') or []:
        message += "Error inserting row %d: %s\n" % (index, err)
    return message
