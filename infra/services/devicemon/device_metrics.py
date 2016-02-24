# -*- coding: utf-8 -*-
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra_libs import ts_mon


cpu_temp_metric = ts_mon.FloatMetric('dev/cpu/temperature',
    description=u"Temperature (°C) of the device's CPU")
battery_temp_metric = ts_mon.FloatMetric('dev/battery/temperature',
    description=u"Temperature (°C) of the device's battery")
battery_charge_metric = ts_mon.FloatMetric('dev/battery/charge',
    description="Charge (%) of the device's battery")
device_status_metric = ts_mon.StringMetric('dev/status',
    description='Status of the device')


def set_cpu_temp(_device, metric_fields):
  cpu_temp = 0 # todo: get cpu temp
  cpu_temp_metric.set(cpu_temp, metric_fields)


def set_battery_temp(_device, metric_fields):
  battery_temp = 0 # todo: get battery temp
  battery_temp_metric.set(battery_temp, metric_fields)


def set_battery_charge(_device, metric_fields):
  battery_charge = 0 # todo: get battery charge
  battery_charge_metric.set(battery_charge, metric_fields)


def set_device_status(_device, metric_fields, status='unknown'):
  device_status_metric.set(status, metric_fields)
