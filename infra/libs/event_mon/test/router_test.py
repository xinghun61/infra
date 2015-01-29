# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.libs.event_mon import router
from infra.libs.event_mon.log_request_lite_pb2 import LogRequestLite


class RouterTests(unittest.TestCase):
  def test_smoke(self):
    # Use dry_run to avoid code that deals with http (including auth).
    r = router._Router(dry_run=True)
    self.assertTrue(r.close())

  def test_push_smoke(self):
    r = router._Router(dry_run=True)

    req = LogRequestLite.LogEventLite()
    req.event_time_ms = router.time_ms()
    req.event_code = 1
    req.event_flow_id = 2
    r.push_event(req)
    self.assertTrue(r.close())

  def test_push_error_handling(self):
    r = router._Router(dry_run=True)
    r.push_event(None)
    self.assertTrue(r.close())
