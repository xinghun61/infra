# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import re
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
ANDROID_DEVICE_FILE_STALENESS_S = 2 * 60 * 60 # 2 hour

PORT_PATH_RE = re.compile(r'\d+\/\d+')


cpu_temp = ts_mon.FloatMetric('dev/mobile/cpu/temperature',
                              description='device CPU temperature in deg C')
batt_temp = ts_mon.FloatMetric('dev/mobile/battery/temperature',
                               description='battery temperature in deg C')
batt_charge = ts_mon.FloatMetric('dev/mobile/battery/charge',
                                 description='percentage charge of battery')
dev_status = ts_mon.StringMetric('dev/mobile/status',
                                 description='operational state of device')
dev_type = ts_mon.StringMetric('dev/mobile/type',
                                description='device hardware or type')
dev_os = ts_mon.StringMetric('dev/mobile/os',
                             description='operating system of the device')
dev_uptime = ts_mon.FloatMetric('dev/mobile/uptime',
                                description='device uptime in seconds',
                                units=ts_mon.MetricsDataUnits.SECONDS)
mem_free = ts_mon.GaugeMetric(
    'dev/mobile/mem/free',
    description='available memory (free + cached + buffers) in kb',
    units=ts_mon.MetricsDataUnits.KIBIBYTES)
mem_total = ts_mon.GaugeMetric(
    'dev/mobile/mem/total',
    description='total memory (device ram - kernel leaks) in kb',
    units=ts_mon.MetricsDataUnits.KIBIBYTES)
proc_count = ts_mon.GaugeMetric('dev/mobile/proc/count',
                                description='process count')

metric_read_status = ts_mon.StringMetric(
    'dev/android_device_metric_read/status',
    description='status of the last metric read')


def get_device_statuses(device_file=ANDROID_DEVICE_FILE, now=None):
  now = now or time.time()
  devices = _load_android_device_file(device_file, now)
  if not devices:
    return

  for device_name, device in devices.iteritems():
    if PORT_PATH_RE.match(device_name):
      logging.warning('Found port path %s as device id. Skipping.',
                      device_name)
      continue

    fields = {'device_id': device_name}

    # Fields with special handling.

    build = device.get('build', {})
    d_type = build.get('build_product',
                       build.get('product.board',
                                 build.get('product.device')))

    battery_temp = device.get('battery', {}).get('temperature')
    battery_temp = battery_temp / 10.0 if battery_temp else None

    status = device.get('state')
    status = 'good' if status == 'available' else status

    for metric, value in (
        (cpu_temp, device.get('temp', {}).get('emmc_therm')),
        (batt_temp, battery_temp),
        (batt_charge, device.get('battery', {}).get('level')),
        (dev_os, build.get('build.id')),
        (dev_status, status),
        (dev_type, d_type),
        (dev_uptime, device.get('uptime')),
        (mem_free, device.get('mem', {}).get('avail')),
        (mem_total, device.get('mem', {}).get('total')),
        (proc_count, device.get('processes'))):
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
