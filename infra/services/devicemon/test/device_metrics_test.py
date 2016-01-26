# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.services.devicemon import device_metrics
from infra_libs import ts_mon

from devil.android import device_utils


class DeviceMetricsTest(unittest.TestCase):
  def setUp(self):
    ts_mon.reset_for_unittest()

  def test_cpu_temp(self):
    device = device_utils.DeviceUtils('fake_serial')
    # todo: mock device interactions
    device_metrics.set_cpu_temp(device, {'device_id': 'fake_serial'})
    cpu_temp = device_metrics.cpu_temp_metric.get({'device_id': 'fake_serial'})

    self.assertEqual(0, cpu_temp)

  def test_battery_temp(self):
    device = device_utils.DeviceUtils('fake_serial')
    # todo: mock device interactions
    device_metrics.set_battery_temp(device, {})
    battery_temp = device_metrics.battery_temp_metric.get({})

    self.assertEqual(0, battery_temp)

  def test_battery_charge(self):
    device = device_utils.DeviceUtils('fake_serial')
    # todo: mock device interactions
    device_metrics.set_battery_charge(device, {})
    battery_charge = device_metrics.battery_charge_metric.get({})

    self.assertEqual(0, battery_charge)

  def test_device_status(self):
    device = device_utils.DeviceUtils('fake_serial')
    # todo: mock device interactions
    device_metrics.set_device_status(device, {}, status='on_fire')
    device_status = device_metrics.device_status_metric.get({})

    self.assertEqual('on_fire', device_status)

  # todo: more tests(!!) once the device interaction is implemented


if __name__ == '__main__':
  unittest.main()
