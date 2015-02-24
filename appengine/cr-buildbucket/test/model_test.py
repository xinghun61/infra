# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from components import utils
from testing_utils import testing

import model


class BuildTest(testing.AppengineTestCase):
  def test_regenerate_lease_key(self):
    build = model.Build(bucket='chromium')
    build.put()
    orig_lease_key = 0
    build.regenerate_lease_key()
    self.assertNotEqual(build.lease_key, orig_lease_key)

  def test_put_with_bad_tags(self):
    build = model.Build(bucket='1', tags=['x'])
    with self.assertRaises(AssertionError):
      build.put()

  def test_new_build_id_generates_monotonicaly_decreasing_ids(self):
    now = datetime.datetime(2015, 2, 24)
    self.mock(utils, 'utcnow', lambda: now)
    last_id = None
    for i in xrange(1000):
      now += datetime.timedelta(seconds=i)
      new_id = model.new_build_id()
      if last_id is not None:
        self.assertLess(new_id, last_id)
      last_id = new_id
