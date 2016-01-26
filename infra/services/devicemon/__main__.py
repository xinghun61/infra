#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Send android device monitoring data to the timeseries monitoring API."""

import logging
import os

from infra.libs.service_utils import outer_loop
from infra.services.devicemon import device_metrics
from infra_libs import ts_mon

from devil.android import device_utils
from devil.android.sdk import adb_wrapper


class DeviceMon(outer_loop.Application):
  def __init__(self):
    super(DeviceMon, self).__init__()
    self.blacklist_file = None

  def add_argparse_options(self, parser):
    super(DeviceMon, self).add_argparse_options(parser)
    parser.add_argument('adb_path', help='Path to adb binary.')
    parser.add_argument('--blacklist-file',
                        help='Path to device blacklist file.')

  def task(self):
    if self.blacklist_file:
      unhealthy_devices = {} # todo: fetch blacklist
    else:
      unhealthy_devices = {}

    try:
      devices = adb_wrapper.AdbWrapper.Devices(desired_state=None)
      for device in devices:
        device = device_utils.DeviceUtils(device)
        fields = {
            'device_id': str(device),
            'device_type': 'type', # todo: get device type
            'device_os': 'os', # todo: get os version
        }
        try:
          device_metrics.set_cpu_temp(device, fields)
          device_metrics.set_battery_temp(device, fields)
          device_metrics.set_battery_charge(device, fields)
          # Assume the blacklist is a more accurate source of truth for device
          # health, so defer to it when determining phone status
          if device not in unhealthy_devices:
            if device.IsOnline():
              device_metrics.set_device_status(device, fields, status='good')
            else:
              logging.warning('Unhealthy device %s not listed in blacklist.',
                              str(device))
              unhealthy_devices[str(device)] = {'reason': device.adb.GetState()}
        except Exception: # todo: change this to catch only device errors
          logging.exception('Error when fetching status of %s.', str(device))
          device_metrics.set_device_status(device, fields, status='unknown')

      for device in unhealthy_devices:
        device_metrics.set_device_status(device, fields,
                                         status=device['reason'])

    finally:
      ts_mon.flush()

    return True

  def sleep_timeout(self):
    return 60

  def main(self, opts):
    # Add adb to the path env var so devil can pick it up
    adb_dir = os.path.dirname(opts.adb_path)
    if adb_dir not in os.environ['PATH'] and os.path.isfile(opts.adb_path):
      os.environ['PATH'] += ':' + adb_dir

    self.blacklist_file = opts.blacklist_file

    return super(DeviceMon, self).main(opts)


if __name__ == '__main__':
  DeviceMon().run()
