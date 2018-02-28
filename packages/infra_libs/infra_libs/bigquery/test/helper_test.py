# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import unittest
from mock import patch

from google.protobuf import empty_pb2
from google.protobuf import struct_pb2
from google.protobuf import timestamp_pb2

from infra_libs.bigquery import helper
from infra_libs.bigquery.test import testmessage_pb2


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

  def test_batch_sizes(self):
    rows = [('a',), ('b',), ('c',)]
    helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows, 0)
    self.mock_create_rows.assert_any_call(self.table, rows)
    helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows, 1)
    self.mock_create_rows.assert_any_call(self.table, [('a',)])
    self.mock_create_rows.assert_any_call(self.table, [('b',)])
    self.mock_create_rows.assert_any_call(self.table, [('c',)])
    helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows,
                     helper.BATCH_LIMIT+1)
    self.mock_create_rows.assert_any_call(self.table, rows)

  def test_send_rows_unsupported_type(self):
    with self.assertRaises(helper.UnsupportedTypeError):
      helper.send_rows(self.bq_client, self.dataset_id, self.table_id, [{}])

  def test_send_rows_message(self):
    rows = [testmessage_pb2.TestMessage(str='a')]
    helper.send_rows(self.bq_client, self.dataset_id, self.table_id, rows)
    expected_rows_arg = [{'num': 0, 'e': 'E0', 'str': u'a'}]
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
    struct0 = struct_pb2.Struct()
    struct0['a'] = 0
    struct1 = struct_pb2.Struct()
    struct1['a'] = 1

    dt0 = datetime.datetime(2018, 2, 20)
    dt1 = datetime.datetime(2018, 2, 21)
    ts0 = timestamp_pb2.Timestamp()
    ts0.FromDatetime(dt0)
    ts1 = timestamp_pb2.Timestamp()
    ts1.FromDatetime(dt1)

    msg = testmessage_pb2.TestMessage(
        str='a',
        strs=['a', 'b'],

        num=1,
        nums=[0, 1, 2],

        nested=testmessage_pb2.NestedMessage(num=1, str='a'),
        nesteds=[
          testmessage_pb2.NestedMessage(num=1, str='a'),
          testmessage_pb2.NestedMessage(num=2, str='b'),
        ],

        empty=empty_pb2.Empty(),
        empties=[empty_pb2.Empty(), empty_pb2.Empty()],

        e=testmessage_pb2.E1,
        es=[testmessage_pb2.E0, testmessage_pb2.E2],

        struct=struct0,
        structs=[struct0, struct1],

        timestamp=ts0,
        timestamps=[ts0, ts1],

        repeated_container=testmessage_pb2.RepeatedContainer(nums=[1, 2]),
    )
    row = helper.message_to_dict(msg)

    expected = {
      'str': u'a',
      'strs': [u'a', u'b'],

      'num': 1L,
      'nums': [0L, 1L, 2L],

      'nested': {'num': 1L, 'str': u'a'},
      'nesteds': [
        {'num': 1L, 'str': u'a'},
        {'num': 2L, 'str': u'b'},
      ],

      # empty messages are omitted

      'e': 'E1',
      'es': ['E0', 'E2'],

      # structs are compared separately.

      'timestamp': dt0.isoformat(),
      'timestamps': [dt0.isoformat(), dt1.isoformat()],

      'repeated_container': {'nums': [1L, 2L]},
    }

    # compare structs as JSON values, not strings.
    self.assertEqual(json.loads(row.pop('struct')), {'a': 0})
    self.assertEqual(
        [json.loads(s) for s in row.pop('structs')],
        [{'a': 0}, {'a': 1}]
    )

    self.assertEqual(row, expected)

  def test_message_to_dict_empty(self):
    row = helper.message_to_dict(testmessage_pb2.TestMessage())
    expected = {'e': 'E0', 'str': u'', 'num': 0}
    self.assertEqual(row, expected)

  def test_message_to_dict_repeated_container_with_no_elems(self):
    row = helper.message_to_dict(testmessage_pb2.TestMessage(
        repeated_container=testmessage_pb2.RepeatedContainer()))
    self.assertNotIn('repeated_container', row)

  def test_message_to_dict_invalid_enum(self):
    with self.assertRaisesRegexp(
        ValueError, '^Invalid value -1 for enum type bigquery.E$'):
      helper.message_to_dict(testmessage_pb2.TestMessage(e=-1))

  def test_message_to_dict_omit_null(self):
    with self.assertRaisesRegexp(
        ValueError, '^Invalid value -1 for enum type bigquery.E$'):
      helper.message_to_dict(testmessage_pb2.TestMessage(e=-1))


if __name__ == '__main__':
  unittest.main()
