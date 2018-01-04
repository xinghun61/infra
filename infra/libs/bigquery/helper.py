# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import threading
import time

from google.protobuf import message as message_pb
from google.protobuf import timestamp_pb2

BATCH_DEFAULT = 500
BATCH_LIMIT = 10000

def message_to_dict(msg):
  """Converts a protobuf message to a dict, with field names as keys.

  msg: an instance of google.protobuf.message.Message.

  RECORD fields, represented as nested messages in the protobuf, are
  formatted as dictionaries.
  TIMESTAMP fields, represented as timestamp_pb2.Timestamp messages in the
  protobuf, are converted to datetime objects.
  """
  row = {}
  for field_desc, val in msg.ListFields():
    if field_desc.label == field_desc.LABEL_REPEATED:
      row[field_desc.name] = [_get_value(elem) for elem in val or []]
    else:
      row[field_desc.name] = _get_value(val)
  return row


def _get_value(value):
  if isinstance(value, timestamp_pb2.Timestamp):
    return value.ToDatetime().isoformat()
  elif isinstance(value, message_pb.Message):
    return message_to_dict(value)
  return value


def send_rows(bq_client, dataset_id, table_id, rows, batch_size=BATCH_DEFAULT):
  """Sends rows to BigQuery.

  Args:
    rows: a list of any of the following
      * tuples: each tuple should contain data of the correct type for each
      schema field on the current table and in the same order as the schema
      fields.
      * google.protobuf.message.Message instance
    bq_client: an instance of google.cloud.bigquery.client.Client
    dataset_id, table_id (str): identifiers for the table to which the rows will
      be inserted
    batch_size (int): the max number of rows to send to BigQuery in a single
      request. Values exceeding the limit will use the limit. Values less than 1
      will use BATCH_DEFAULT.

  Please use google.protobuf.message.Message instances moving forward.
  Tuples are deprecated.
  """
  if batch_size > BATCH_LIMIT:
    batch_size = BATCH_LIMIT
  elif batch_size <= 0:
    batch_size = BATCH_DEFAULT
  for i, row in enumerate(rows):
    if isinstance(row, tuple):
      continue
    elif isinstance(row, message_pb.Message):
      rows[i] = message_to_dict(row)
    else:
      raise UnsupportedTypeError(type(row).__name__)
  table = bq_client.get_table(bq_client.dataset(dataset_id).table(table_id))
  for row_set in _batch(rows, batch_size):
    insert_errors = bq_client.create_rows(table, row_set)
    if insert_errors:
      logging.error('Failed to send event to bigquery: %s', insert_errors)
      raise BigQueryInsertError(insert_errors)


def _batch(rows, batch_size):
  for i in xrange(0, len(rows), batch_size):
    yield rows[i:i + batch_size]


class UnsupportedTypeError(Exception):
  """BigQueryHelper only supports row representations described by send_rows.

  row_type: string representation of type.
  """
  def __init__(self, row_type):
    msg = 'Unsupported row type for BigQueryHelper.send_rows: %s' % row_type
    super(UnsupportedTypeError, self).__init__(msg)


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
