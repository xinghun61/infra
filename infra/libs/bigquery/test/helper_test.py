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
    bq_client = mock.Mock()
    self.bq_helper = helper.BigQueryHelper(bq_client)

    self.dataset_id = 'test_dataset'
    self.table_id = 'test_table'
    self.table = bq_client.get_table(
        bq_client.dataset(self.dataset_id).table(self.table_id))
    self.mock_create_rows = bq_client.create_rows
    self.mock_create_rows.return_value = None

  def test_send_rows(self):
    rows = ['a', 'b', 'c']
    self.bq_helper.send_rows(self.dataset_id, self.table_id, rows)
    self.mock_create_rows.assert_any_call(self.table, rows)

  def test_send_rows_with_errors(self):
    rows = ['a', 'b', 'c']
    self.mock_create_rows.return_value = [
        {
            'index': 0,
            'errors': ['some err'],
        },
    ]
    with self.assertRaises(helper.BigQueryInsertError):
      self.bq_helper.send_rows(self.dataset_id, self.table_id, rows)


if __name__ == '__main__':
  unittest.main()
