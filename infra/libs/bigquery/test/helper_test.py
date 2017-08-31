# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from mock import patch
from infra.libs.bigquery import helper


class TestBigQueryHelper(unittest.TestCase):
  def setUp(self):
    super(TestBigQueryHelper, self).setUp()
    now = lambda: 0
    bq_client = mock.Mock()
    self.bq_helper = helper.BigQueryHelper(bq_client, now=now)

    self.dataset_id = 'test_dataset'
    self.table_id = 'test_table'
    self.mock_insert_data = bq_client.dataset(self.dataset_id).table(
        self.table_id).insert_data
    self.mock_insert_data.return_value = None

  @patch('os.urandom', new=lambda _: '123')
  def test_generate_insert_id(self):
    s = '123'.encode('hex')
    self.assertEqual(self.bq_helper.generate_insert_id(), ':%s:0:0' % s)
    self.assertEqual(self.bq_helper.generate_insert_id('prefix'),
                     'prefix:%s:0:1' % s)

  def test_send_rows(self):
    rows = ['a', 'b', 'c']
    row_ids = [1, 2, 3]
    self.bq_helper.send_rows(self.dataset_id, self.table_id, rows, row_ids)
    self.mock_insert_data.assert_any_call(rows, row_ids)

  @patch('os.urandom', new=lambda _: '123')
  def test_send_rows_without_ids(self):
    s = '123'.encode('hex')
    rows = ['a', 'b', 'c']
    expected_row_ids = [':%s:0:%d' % (s, i) for i in range(3)]
    self.bq_helper.send_rows(self.dataset_id, self.table_id, rows)
    self.mock_insert_data.assert_any_call(rows, expected_row_ids)

  def test_send_rows_with_errors(self):
    rows = ['a', 'b', 'c']
    self.mock_insert_data.return_value = [
        {
            'index': 0,
            'errors': ['some err'],
        },
    ]
    with self.assertRaises(helper.BigQueryInsertError):
      self.bq_helper.send_rows(self.dataset_id, self.table_id, rows)


if __name__ == '__main__':
  unittest.main()
