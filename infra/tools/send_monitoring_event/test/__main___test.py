# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import unittest

import infra.tools.send_monitoring_event.__main__ as send_event


class TestArgumentParsing(unittest.TestCase):
  def test_smoke(self):
    send_event.get_arguments(['--event-mon-service-name', 'thing'])
