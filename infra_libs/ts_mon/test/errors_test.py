# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra_libs.ts_mon import errors


class ErrorsTest(unittest.TestCase):

  def test_decreasing_value(self):
    with self.assertRaises(errors.MonitoringDecreasingValueError) as e:
      raise errors.MonitoringDecreasingValueError('test', 1, 0)
    str(e.exception)

  def test_duplicate_registration(self):
    with self.assertRaises(errors.MonitoringDuplicateRegistrationError) as e:
      raise errors.MonitoringDuplicateRegistrationError('test')
    str(e.exception)

  def test_increment_unset_value(self):
    with self.assertRaises(errors.MonitoringIncrementUnsetValueError) as e:
      raise errors.MonitoringIncrementUnsetValueError('test')
    str(e.exception)

  def test_invalid_value_type(self):
    with self.assertRaises(errors.MonitoringInvalidValueTypeError) as e:
      raise errors.MonitoringInvalidValueTypeError('test', 'foo')
    str(e.exception)

  def test_invalid_field_type(self):
    with self.assertRaises(errors.MonitoringInvalidFieldTypeError) as e:
      raise errors.MonitoringInvalidFieldTypeError('test', 'foo', 'bar')
    str(e.exception)

  def test_too_many_fields(self):
    with self.assertRaises(errors.MonitoringTooManyFieldsError) as e:
      raise errors.MonitoringTooManyFieldsError('test', {'foo': 'bar'})
    str(e.exception)

  def test_no_configured_monitor(self):
    with self.assertRaises(errors.MonitoringNoConfiguredMonitorError) as e:
      raise errors.MonitoringNoConfiguredMonitorError('test')
    str(e.exception)

  def test_no_configured_monitor_flush(self):
    with self.assertRaises(errors.MonitoringNoConfiguredMonitorError) as e:
      raise errors.MonitoringNoConfiguredMonitorError(None)
    str(e.exception)

  def test_no_configured_target(self):
    with self.assertRaises(errors.MonitoringNoConfiguredTargetError) as e:
      raise errors.MonitoringNoConfiguredTargetError('test')
    str(e.exception)
