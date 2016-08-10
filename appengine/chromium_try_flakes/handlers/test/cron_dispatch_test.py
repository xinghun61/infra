# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
from testing_utils import testing

import main  # Fiddles sys.path so must come first.

from handlers import cron_dispatch


class TestCronDispatch(testing.AppengineTestCase):
  app_module = main.app

  def test_triggers_cron_job(self):
    fetch_cq_status_mock = mock.Mock()
    cron_dispatch.commands['fetch_cq_status'] = fetch_cq_status_mock
    self.test_app.get('/cron/fetch_cq_status')
    self.assertEqual(fetch_cq_status_mock.call_count, 1)
