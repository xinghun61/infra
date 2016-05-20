# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import unittest

from infra.services.sysmon import android_device_metrics
from infra_libs import ts_mon

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class AndroidDeviceMetricTest(unittest.TestCase):
  def setUp(self):
    ts_mon.reset_for_unittest()

    self.nonexistent_file = os.path.join(DATA_DIR, 'brananas.json')
    self.normal_file = os.path.join(DATA_DIR, 'normal.json')
    self.invalid_json_file = os.path.join(
        DATA_DIR, 'invalid_files', 'invalid_json_android_device_status.json')
    self.not_dict_file = os.path.join(
        DATA_DIR, 'invalid_files', 'not_dict_android_device_status.json')
    self.invalid_version_file = os.path.join(
        DATA_DIR, 'invalid_files', 'invalid_version_android_device_status.json')
    self.valid_file = os.path.join(
        DATA_DIR, 'valid_files', 'android_device_status.json')
    self.no_temp_file = os.path.join(
        DATA_DIR, 'valid_files', 'no_temp_android_device_status.json')

    # A test device in the representative json file.
    self.device_id = '06c38708006afff3'

  def _assert_read_status(self, should_equal='good'):
    read_status = android_device_metrics.metric_read_status.get()
    self.assertEqual(read_status, should_equal)

  def _assert_all_none(self, device_id):
    fields = {'device_id': device_id}

    self.assertIsNone(android_device_metrics.batt_charge.get(fields=fields))
    self.assertIsNone(android_device_metrics.batt_temp.get(fields=fields))
    self.assertIsNone(android_device_metrics.cpu_temp.get(fields=fields))
    self.assertIsNone(android_device_metrics.dev_os.get(fields=fields))
    self.assertIsNone(android_device_metrics.dev_status.get(fields=fields))
    self.assertIsNone(android_device_metrics.dev_uptime.get(fields=fields))

  def test_no_file(self):
    android_device_metrics.get_device_statuses(self.nonexistent_file)
    self._assert_read_status(should_equal='not_found')
    self._assert_all_none(self.device_id)

  def test_invalid_json(self):
    android_device_metrics.get_device_statuses(self.invalid_json_file)
    self._assert_read_status(should_equal='invalid_json')
    self._assert_all_none(self.device_id)

  def test_not_dict_file(self):
    android_device_metrics.get_device_statuses(self.not_dict_file)
    self._assert_read_status(should_equal='invalid_json')
    self._assert_all_none(self.device_id)

  def test_invalid_version(self):
    android_device_metrics.get_device_statuses(self.invalid_version_file)
    self._assert_read_status(should_equal='invalid_version')
    self._assert_all_none(self.device_id)

  def test_stale(self):
    with open(self.valid_file) as f:
      file_time = float(json.load(f)['timestamp'])
    stale_time = (
        10 + file_time + android_device_metrics.ANDROID_DEVICE_FILE_STALENESS_S)

    android_device_metrics.get_device_statuses(
        self.valid_file, now=stale_time)
    self._assert_read_status(should_equal='stale_file')
    self._assert_all_none(self.device_id)

  def test_good(self):
    with open(self.valid_file) as f:
      file_time = float(json.load(f)['timestamp'])

    android_device_metrics.get_device_statuses(
        self.valid_file, now=file_time)
    self._assert_read_status(should_equal='good')

    fields = {'device_id': self.device_id}

    self.assertEqual(
        android_device_metrics.batt_charge.get(fields=fields), 100.0)
    self.assertEqual(android_device_metrics.batt_temp.get(fields=fields), 26.8)
    self.assertEqual(android_device_metrics.cpu_temp.get(fields=fields), 26)
    self.assertEqual(android_device_metrics.dev_os.get(fields=fields), 'KTU84P')
    self.assertEqual(
        android_device_metrics.dev_status.get(fields=fields), 'good')
    self.assertEqual(
        android_device_metrics.dev_uptime.get(fields=fields), 2162.74)

  def test_no_metric_sent(self):
    with open(self.no_temp_file) as f:
      file_time = float(json.load(f)['timestamp'])

    android_device_metrics.get_device_statuses(
        self.no_temp_file, now=file_time)
    self._assert_read_status(should_equal='good')

    fields = {'device_id': self.device_id}
    self.assertIsNone(android_device_metrics.cpu_temp.get(fields=fields))
