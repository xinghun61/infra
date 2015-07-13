# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from infra.services.mastermon import monitor


class MasterMonitorTest(unittest.TestCase):
  def test_poll(self):
    mock_poller_class = mock.Mock()
    mock_poller = mock_poller_class.return_value

    class MasterMonitor(monitor.MasterMonitor):
      POLLER_CLASSES = [mock_poller_class]

    m = MasterMonitor('http://example.com')

    mock_poller.poll.return_value = True
    m.poll()
    self.assertTrue(m.up.get())

    mock_poller.poll.return_value = False
    m.poll()
    self.assertFalse(m.up.get())

  def test_poll_with_name(self):
    mock_poller_class = mock.Mock()
    mock_poller = mock_poller_class.return_value

    class MasterMonitor(monitor.MasterMonitor):
      POLLER_CLASSES = [mock_poller_class]

    m = MasterMonitor('http://example.com', 'foobar')

    mock_poller.poll.return_value = True
    m.poll()
    self.assertTrue(m.up.get({'master': 'foobar'}))

    mock_poller.poll.return_value = False
    m.poll()
    self.assertFalse(m.up.get({'master': 'foobar'}))


class MastermapTest(unittest.TestCase):
  def test_create_from_mastermap(self):
    m = monitor._create_from_mastermap([
      {'port': 1234, 'dirname': 'master.foo.bar'},
      {'port': 5678, 'dirname': 'master.baz'},
    ])

    self.assertEquals(2, len(m))
    self.assertTrue(m[0]._pollers[0]._url.startswith('http://localhost:1234/'))
    self.assertTrue(m[1]._pollers[0]._url.startswith('http://localhost:5678/'))
    self.assertEquals({'master': 'master.foo.bar'}, m[0]._pollers[0].fields())
    self.assertEquals({'master': 'master.baz'}, m[1]._pollers[0].fields())

