# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from analysis.analysis_testcase import AnalysisTestCase
from analysis.log import Log
from analysis.log import Message


class MessageTest(AnalysisTestCase):
  """Tests Message class."""

  def testToDict(self):
    """Tests ``ToDict`` method."""
    message = Message('name', 'dummy_message')
    self.assertDictEqual(message.ToDict(), {'name': 'dummy_message'})


class LogTest(AnalysisTestCase):
  """Tests Log class."""

  def setUp(self):
    super(LogTest, self).setUp()
    self.log = Log()

  def testInfo(self):
    """Tests log info."""
    self.log.info('name1', 'info1')
    self.log.info('name2', 'info2')
    self.assertEqual(self.log.info_log, [Message('name1', 'info1'),
                                              Message('name2', 'info2')])
  def testWarning(self):
    """Tests log warning."""
    self.log.warning('name1', 'warning1')
    self.log.warning('name2', 'warning2')
    self.assertEqual(self.log.warning_log,
                     [Message('name1', 'warning1'),
                      Message('name2', 'warning2')])

  def testError(self):
    """Tests log error."""
    self.log.error('name1', 'error1')
    self.log.error('name2', 'error2')
    self.assertEqual(self.log.error_log,
                     [Message('name1', 'error1'),
                      Message('name2', 'error2')])

  def testToDict(self):
    """Tests ``ToDict`` method."""
    self.log.info('info_name', 'some info...')
    self.log.warning('warning_name', 'some warning...')
    self.log.error('error_name1', 'exception...')
    self.log.error('error_name2', 'exceptions...')

    self.assertDictEqual(
        self.log.ToDict(),
        {
            'info': {'info_name': 'some info...'},
            'warning': {'warning_name': 'some warning...'},
            'error': {'error_name1': 'exception...',
                      'error_name2': 'exceptions...'}
        })
