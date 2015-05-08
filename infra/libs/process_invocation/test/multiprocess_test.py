# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import multiprocessing
from testing_support import auto_stub

from infra.libs.process_invocation import multiprocess


class TestMultiprocess(auto_stub.TestCase):
  def setUp(self):
    super(TestMultiprocess, self).setUp()

    self.calls = set()
    class FakePool(object):
      def __init__(self, calls):
        self.calls = calls

      def close(self):
        self.calls.add('close')

      def terminate(self):
        self.calls.add('terminate')

      def join(self):
        self.calls.add('join')

    def pool_maker(*_args, **_kwargs):
      return FakePool(self.calls)

    self.mock(multiprocessing, 'Pool', pool_maker)

  def testMultiprocess(self):
    with multiprocess.MultiPool(16) as _pool:
      pass

    self.assertIn('close', self.calls)
    self.assertIn('join', self.calls)
    self.assertNotIn('terminate', self.calls)

  def testMultiprocessTermiantes(self):
    with self.assertRaises(RuntimeError):
      with multiprocess.MultiPool(16) as _pool:
        raise RuntimeError('a super bad error')

    self.assertIn('terminate', self.calls)
    self.assertIn('join', self.calls)
