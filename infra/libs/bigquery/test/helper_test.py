# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest
from mock import patch

from google.protobuf import timestamp_pb2

from infra.libs.bigquery import helper
from infra.libs.bigquery.test import testmessage_pb2


class TestBigQueryHelper(unittest.TestCase):
  def setUp(self):
    super(TestBigQueryHelper, self).setUp()
    self.bq_client = mock.Mock()

    self.dataset_id = 'test_dataset'
    self.table_id = 'test_table'
    self.table = self.bq_client.get_table(
        self.bq_client.dataset(self.dataset_id).table(self.table_id))
    self.mock_create_rows = self.bq_client.create_rows
    self.mock_create_rows.return_value = None

  def test_send_rows_tuple(self):
    rows = [('a',), ('b',), ('c',)]
    helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows)
    self.mock_create_rows.assert_any_call(self.table, rows)

  def test_send_rows_unsupported_type(self):
    with self.assertRaises(helper.UnsupportedTypeError):
      helper.send_rows(self.bq_client, self.dataset_id, self.table_id, [{}])

  def test_send_rows_message(self):
    rows = [testmessage_pb2.TestMessage(name='test_name')]
    helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows)
    expected_rows_arg = [{'name': u'test_name'}]
    self.mock_create_rows.assert_any_call(self.table, expected_rows_arg)

  def test_send_rows_with_errors(self):
    rows = [('a',), ('b',), ('c',)]
    self.mock_create_rows.return_value = [
        {
            'index': 0,
            'errors': ['some err'],
        },
    ]
    with self.assertRaises(helper.BigQueryInsertError):
      helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows)

  def test_message_to_dict(self):
    msg = testmessage_pb2.TestMessage(
        name='test_name',
        nesteds=[
          testmessage_pb2.NestedMessage(
              timestamps=[timestamp_pb2.Timestamp(), timestamp_pb2.Timestamp()],
          ),
          testmessage_pb2.NestedMessage(),
        ],
    )
    row = helper.message_to_dict(msg)
    expected = {
        'name': u'test_name',
        'nesteds': [
            {'timestamps': [timestamp_pb2.Timestamp().ToDatetime().isoformat(),
                            timestamp_pb2.Timestamp().ToDatetime().isoformat()],
            },
            {},
        ],
    }
    self.assertEqual(row, expected)


if __name__ == '__main__':
  unittest.main()
