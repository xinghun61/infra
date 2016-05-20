# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import socket
import time


from infra_libs import ts_mon
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import targets


ANDROID_DEVICE_FILE_VERSION = 1

ANDROID_PREVIOUS_DEVICE_FILE_VERSION = ANDROID_DEVICE_FILE_VERSION - 1
ANDROID_DEVICE_FILE = os.path.join(os.path.expanduser('~'),
                                   'android_device_status.json')

# Don't read a file older than this many seconds.
ANDROID_DEVICE_FILE_STALENESS_S = 120


cpu_temp = ts_mon.FloatMetric('dev/cpu/temperature',
                              description='device CPU temperature in deg C')
batt_temp = ts_mon.FloatMetric('dev/battery/temperature',
                               description='battery temperature in deg C')
batt_charge = ts_mon.FloatMetric('dev/battery/charge',
                                 description='percentage charge of battery')
dev_status = ts_mon.StringMetric('dev/status',
                                 description='operational state of device')
dev_os = ts_mon.StringMetric('dev/os',
                             description='operating system of the device')
dev_uptime = ts_mon.FloatMetric('dev/device_uptime',
                                description='device uptime in seconds')

metric_read_status = ts_mon.StringMetric(
    'dev/android_device_metric_read/status',
    description='status of the last metric read')


def get_device_statuses(device_file=ANDROID_DEVICE_FILE, now=None):
  now = now or time.time()
  devices = _load_android_device_file(device_file, now)
  if not devices:
    return

  for device_name, device in devices.iteritems():
    fields = {'device_id': device_name}

    # Fields with special handling.

    battery_temp = device.get('battery', {}).get('temperature')
    battery_temp = battery_temp / 10.0 if battery_temp else None

    status = device.get('state')
    status = 'good' if status == 'available' else status

    for metric, value in (
        (cpu_temp, device.get('temp', {}).get('emmc_therm')),
        (batt_temp, battery_temp),
        (batt_charge, device.get('battery', {}).get('level')),
        (dev_status, status),
        (dev_os, device.get('build', {}).get('build.id')),
        (dev_uptime, device.get('uptime'))):
      if value is not None:
        metric.set(value, fields=fields)


def _load_android_device_file(device_file, now):
  """Load the android device file and check for errors or staleness."""
  try:
    with open(device_file) as f:
      file_data = f.read()  # pragma: no cover
  except (IOError, OSError):
    # File isn't there, not an Android bot.
    metric_read_status.set('not_found')
    logging.debug('Android device file %s not found', device_file)
    return []

  try:
    json_data = json.loads(file_data)
  except ValueError as e:
    metric_read_status.set('invalid_json')
    logging.error('Android device file %s invalid json: %s',
                  device_file, e)
    return []

  if not isinstance(json_data, dict):
    metric_read_status.set('invalid_json')
    logging.error('Android device file %s is not a dict', device_file)
    return []

  if json_data.get('version') not in (
      ANDROID_DEVICE_FILE_VERSION,
      ANDROID_PREVIOUS_DEVICE_FILE_VERSION):
    metric_read_status.set('invalid_version')
    logging.error('Android device file %s is version %s, not %s',
                  device_file, json_data.get('version'),
                  ANDROID_DEVICE_FILE_VERSION)
    return []

  timestamp = json_data.get('timestamp', 0)
  if now >= timestamp + ANDROID_DEVICE_FILE_STALENESS_S:
    metric_read_status.set('stale_file')
    logging.error('Android device file %s is %ss stale (max %ss)',
                  device_file, now - timestamp,
                  ANDROID_DEVICE_FILE_STALENESS_S)
    return []

  metric_read_status.set('good')
  return json_data.get('devices', [])
