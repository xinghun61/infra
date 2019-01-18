# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb

from testing_utils import testing
from test import test_util

from proto import build_pb2
from proto import common_pb2
import model
import v2


class BuildTest(testing.AppengineTestCase):

  def test_regenerate_lease_key(self):
    build = test_util.build()
    build.put()
    build.regenerate_lease_key()
    self.assertNotEqual(build.lease_key, 0)

  def test_put_with_bad_tags(self):
    build = test_util.build()
    build.tags.append('x')
    with self.assertRaises(AssertionError):
      build.put()

  def test_create_build_id_generates_monotonically_decreasing_ids(self):
    now = datetime.datetime(2015, 2, 24)
    ids = []
    for i in xrange(1000):
      now += datetime.timedelta(seconds=i)
      ids.extend(model.create_build_ids(now, 5))
    self.assertEqual(ids, sorted(ids, reverse=True))

  def test_build_id_range(self):
    time_low = datetime.datetime(2015, 1, 1)
    time_high = time_low + datetime.timedelta(seconds=10)
    id_low, id_high = model.build_id_range(time_low, time_high)
    unit = model._TIME_RESOLUTION

    ones = (1 << model._BUILD_ID_SUFFIX_LEN) - 1
    for suffix in (0, ones):

      def in_range(t):
        build_id = model._id_time_segment(t) | suffix
        return id_low <= build_id < id_high

      self.assertFalse(in_range(time_low - unit))
      self.assertTrue(in_range(time_low))
      self.assertTrue(in_range(time_low + unit))

      self.assertTrue(in_range(time_high - unit))
      self.assertFalse(in_range(time_high))
      self.assertFalse(in_range(time_high + unit))

  def test_build_steps_without_step_container(self):
    build_steps = model.BuildSteps(
        key=model.BuildSteps.key_for(ndb.Key(model.Build, 1)),
    )
    with self.assertRaises(AssertionError):
      build_steps.put()

  def test_proto_population(self):
    build = model.Build(
        bucket_id='chromium/try',
        proto=build_pb2.Build(),
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        create_time=datetime.datetime(2019, 1, 1),
        start_time=datetime.datetime(2019, 1, 2),
        complete_time=datetime.datetime(2019, 1, 3),
        update_time=datetime.datetime(2019, 1, 3),
    )
    build.put()
    self.assertEqual(build.proto.status, common_pb2.SUCCESS)
    self.assertEqual(build.proto.start_time.ToDatetime(), build.start_time)
    self.assertEqual(build.proto.end_time.ToDatetime(), build.complete_time)
    self.assertEqual(build.proto.update_time.ToDatetime(), build.update_time)
