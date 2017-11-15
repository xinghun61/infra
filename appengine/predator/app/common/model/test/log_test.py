# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.appengine_testcase import AppengineTestCase
from common.model.log import Log


class LogTest(AppengineTestCase):
  """tests log class."""

  def setUp(self):
    super(LogTest, self).setUp()
    self.ids = {'id': '123'}
    self.log = Log.Create(self.ids)
    self.log.put()

  def testGet(self):
    """Tests ``Get`` method."""
    self.assertEqual(Log.Get(self.ids), self.log)

  def testLog(self):
    """Tests log info."""
    self.log.Log('name1', 'error1', 'error')
    self.log.Log('name2', 'info2', 'info')
    self.assertEqual(self.log.logs,
                     [{'name': 'name1', 'message': 'error1', 'level': 'error'},
                      {'name': 'name2', 'message': 'info2', 'level': 'info'}])

  def testReset(self):
    """Tests ``Reset`` method."""
    self.log.Log('info_name', 'dummy info.', 'info')
    self.assertNotEqual(self.log.logs, [])
    self.log.Reset()
    self.assertEqual(self.log.logs, [])
