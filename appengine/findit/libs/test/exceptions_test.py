# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs import exceptions


@exceptions.EnhanceMessage
def _ProblematicFunction():
  raise NotImplementedError('my message')  # Trigger an exception intentionally.


class ExceptionsTest(unittest.TestCase):

  def testEnhanceMessage(self):
    with self.assertRaisesRegexp(
        NotImplementedError,
        ('^libs/test/exceptions\_test\.py:\d+ \_ProblematicFunction '
         '\$\$ my message$')):
      _ProblematicFunction()
