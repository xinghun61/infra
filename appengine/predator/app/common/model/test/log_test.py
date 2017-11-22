# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.appengine_testcase import AppengineTestCase
from common.model.log import Log


class LogTest(AppengineTestCase):
  """tests log class."""

  def testGet(self):
    """Tests ``Get`` method."""
    ids = {'id': 'log_test_get'}
    log = Log.Create(ids)
    log.put()

    self.assertEqual(Log.Get(ids), log)

  def testLog(self):
    """Tests log info."""
    log = Log.Create({'id': 'log_test_log'})
    log.Reset()
    log.Log('name1', 'error1', 'error')
    log.Log('name2', 'info2', 'info')
    self.assertEqual(log.logs,
                     [{'name': 'name1', 'message': 'error1', 'level': 'error'},
                      {'name': 'name2', 'message': 'info2', 'level': 'info'}])

  def testReset(self):
    """Tests ``Reset`` method."""
    log = Log.Create({'id': 'log_test_reset'})
    log.Log('info_name', 'dummy info.', 'info')
    self.assertNotEqual(log.logs, [])
    log.Reset()
    self.assertEqual(log.logs, [])
