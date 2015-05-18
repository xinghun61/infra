# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import logging

from infra.libs import logs

class InfraFilterTest(unittest.TestCase):

  def test_infrafilter_adds_correct_fields(self):
    record = logging.makeLogRecord({})
    infrafilter = logs.InfraFilter('US/Pacific')
    infrafilter.filter(record)
    self.assertTrue(hasattr(record, "severity"))
    self.assertTrue(hasattr(record, "iso8601"))
