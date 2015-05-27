# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from infra_libs.event_mon import router
from infra_libs.event_mon.log_request_lite_pb2 import LogRequestLite


DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class RouterTests(unittest.TestCase):
  def test_smoke(self):
    # Use dry_run to avoid code that deals with http (including auth).
    r = router._Router({}, endpoint=None)
    self.assertTrue(r.close())

  def test_smoke_with_credentials(self):
    cache = {'service_account_creds':
             os.path.join(DATA_DIR, 'valid_creds.json'),
             'service_accounts_creds_root': 'whatever.the/other/is/absolute'}
    r = router._Router(cache, endpoint='https://any.where')
    self.assertTrue(r.close())

  def test_push_smoke(self):
    r = router._Router({}, endpoint=None)

    req = LogRequestLite.LogEventLite()
    req.event_time_ms = router.time_ms()
    req.event_code = 1
    req.event_flow_id = 2
    r.push_event(req)
    self.assertTrue(r.close())

  def test_push_error_handling(self):
    r = router._Router({}, endpoint=None)
    r.push_event(None)
    self.assertTrue(r.close())
