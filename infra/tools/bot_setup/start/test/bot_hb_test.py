# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=F0401,W0212

import time
import unittest

from infra.tools.bot_setup.start import bot_hb


class UnexpectedCall(Exception):
  pass
class UnusedSeeds(Exception):
  pass


class HeartbeatMock(object):
  """This mocks the heartbeat module."""
  def __init__(self):
    self.seeds = {}
    self.expectations = []

  def expect(self, fn, result):
    self.seeds.setdefault(fn, [])
    self.seeds[fn].append(result)

  def _mocked(self, fn):
    def _inner(*args, **kwargs):
      self.expectations.append({
          'called': fn,
          'args': list(args),
          'kwargs': kwargs
      })
      if self.seeds.get(fn):
        return self.seeds.get(fn).pop(0)
      else:
        msg = '%s() called unexpectedly\n' % fn
        msg += '  args: %s\n' % str(args)
        msg += '  kwargs: %s' % str(kwargs)
        raise UnexpectedCall(msg)
    return _inner

  def __getattr__(self, fn):
    return self._mocked(fn)

  def check_seeds(self):
    if any(self.seeds.values()):
      msg = ''
      for k, v in self.seeds.iteritems():
        if v:
          msg += '%s: %s' % (k, str(v))
      raise UnusedSeeds(msg)


class TestHeartbeats(unittest.TestCase):
  def setUp(self):
    super(TestHeartbeats, self).setUp()
    self.hb_mock = HeartbeatMock()
    self.hb_mock.expect('get_secret', 'Totally a secret')
    self.hb = bot_hb.HeartbeatRunner(
        'test_slave', '/some/dir', heartbeat_cls=self.hb_mock)
    self.old_time_time = time.time
    setattr(time, 'time', lambda: 999999.0)

  def tearDown(self):
    setattr(time, 'time', self.old_time_time)

  def test_send_heartbeat(self):
    self.hb_mock.expect('get_id', 'Fake ID')
    self.hb_mock.expect('get_hashed_message', {'msg': 'Fake'})
    self.hb_mock.expect('send', 0)
    self.hb.set('foo', 'bar')
    self.hb._send_heartbeat()
    self.hb_mock.check_seeds()
    return sorted(self.hb_mock.expectations)

  def test_send_heartbeat_402(self):
    self.hb_mock.expect('get_id', 'Fake ID')
    self.hb_mock.expect('get_hashed_message', {'msg': 'Fake'})
    self.hb_mock.expect('send', 402)
    self.hb_mock.expect('send', 0)
    self.hb.set('foo', 'bar')
    self.hb._send_heartbeat()
    self.hb_mock.check_seeds()
    return sorted(self.hb_mock.expectations)

  def test_unexpected_call(self):
    self.assertRaises(UnexpectedCall, self.hb._send_heartbeat)

  def test_unexpected_seed(self):
    self.hb_mock.expect('foo', 'bar')
    self.assertRaises(UnusedSeeds, self.hb_mock.check_seeds)

