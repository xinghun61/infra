# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from testing_utils import testing

import common


class CommonTest(testing.auto_stub.TestCase):

  def test_payload_stats(self):
    data = 'c00kedbeef'
    res = "type=<type 'str'>, 10 bytes, md5=407ab662183805731696989975459a9f"
    self.assertEquals(res, common.payload_stats(data))
