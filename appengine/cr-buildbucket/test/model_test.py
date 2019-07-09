# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest
import mock

from google.appengine.ext import ndb
from google.protobuf import timestamp_pb2

from testing_utils import testing
from test import test_util

from proto import build_pb2
from proto import common_pb2
from proto import step_pb2
import bbutil
import model


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


class TestStatusConversion(unittest.TestCase):

  def compare(self, build):
    actual = model.Build(proto=build.proto)
    actual.update_v1_status_fields()
    self.assertEqual(actual.status_legacy, build.status_legacy)
    self.assertEqual(actual.result, build.result)
    self.assertEqual(actual.failure_reason, build.failure_reason)
    self.assertEqual(actual.cancelation_reason, build.cancelation_reason)

  def test_started(self):
    self.compare(
        model.Build(
            proto=build_pb2.Build(status=common_pb2.STARTED),
            status_legacy=model.BuildStatus.STARTED,
        ),
    )

  def test_success(self):
    self.compare(
        model.Build(
            proto=build_pb2.Build(status=common_pb2.SUCCESS),
            status_legacy=model.BuildStatus.COMPLETED,
            result=model.BuildResult.SUCCESS
        ),
    )

  def test_build_failure(self):
    self.compare(
        model.Build(
            proto=build_pb2.Build(status=common_pb2.FAILURE),
            status_legacy=model.BuildStatus.COMPLETED,
            result=model.BuildResult.FAILURE,
            failure_reason=model.FailureReason.BUILD_FAILURE
        ),
    )

  def test_infra_failure(self):
    self.compare(
        model.Build(
            proto=build_pb2.Build(status=common_pb2.INFRA_FAILURE),
            status_legacy=model.BuildStatus.COMPLETED,
            result=model.BuildResult.FAILURE,
            failure_reason=model.FailureReason.INFRA_FAILURE
        ),
    )

  def test_canceled(self):
    self.compare(
        model.Build(
            proto=build_pb2.Build(status=common_pb2.CANCELED),
            status_legacy=model.BuildStatus.COMPLETED,
            result=model.BuildResult.CANCELED,
            cancelation_reason=model.CancelationReason.CANCELED_EXPLICITLY
        ),
    )

  def test_timeout(self):
    self.compare(
        model.Build(
            proto=build_pb2.Build(
                status=common_pb2.INFRA_FAILURE,
                status_details=dict(timeout=dict())
            ),
            status_legacy=model.BuildStatus.COMPLETED,
            result=model.BuildResult.CANCELED,
            cancelation_reason=model.CancelationReason.TIMEOUT
        ),
    )


class ToBuildProtosTests(testing.AppengineTestCase):

  def to_proto(
      self,
      build,
      load_tags=False,
      load_input_properties=False,
      load_output_properties=False,
      load_steps=False,
      load_infra=False
  ):
    proto = build_pb2.Build()
    model.builds_to_protos_async(
        [(build, proto)],
        load_tags=load_tags,
        load_input_properties=load_input_properties,
        load_output_properties=load_output_properties,
        load_steps=load_steps,
        load_infra=load_infra,
    ).get_result()
    return proto

  def test_tags(self):
    build = test_util.build()
    self.assertFalse(build.proto.tags)
    build.tags = [
        'a:b',
        'builder:hidden',
    ]

    actual = self.to_proto(build, load_tags=True)
    self.assertEqual(
        list(actual.tags), [common_pb2.StringPair(key='a', value='b')]
    )

  def test_steps(self):
    build = test_util.build(id=1)
    steps = [
        step_pb2.Step(name='a', status=common_pb2.SUCCESS),
        step_pb2.Step(name='b', status=common_pb2.STARTED),
    ]
    build_steps = model.BuildSteps.make(build_pb2.Build(id=1, steps=steps))
    build_steps.put()

    actual = self.to_proto(build, load_steps=True)
    self.assertEqual(list(actual.steps), steps)

  def test_out_props(self):
    props = bbutil.dict_to_struct({'a': 'b'})
    build = test_util.build()
    model.BuildOutputProperties(
        key=model.BuildOutputProperties.key_for(build.key),
        properties=props.SerializeToString(),
    ).put()

    actual = self.to_proto(build, load_output_properties=True)
    self.assertEqual(actual.output.properties, props)

  def test_in_props(self):
    props = bbutil.dict_to_struct({'a': 'b'})
    build = test_util.build(input=dict(properties=props))

    actual = self.to_proto(build, load_input_properties=True)
    self.assertEqual(actual.input.properties, props)

  def test_infra(self):
    bundle = test_util.build_bundle(
        infra=dict(swarming=dict(hostname='swarming.example.com'))
    )
    bundle.infra.put()
    actual = self.to_proto(bundle.build, load_infra=True)
    self.assertEqual(actual.infra.swarming.hostname, 'swarming.example.com')

  def test_load_bundle_with_build_id(self):
    bundle = test_util.build_bundle(id=1)
    bundle.put()
    actual = model.BuildBundle.get(1, infra=True)
    self.assertEqual(actual.build.key.id(), 1)
    self.assertEqual(actual.infra, bundle.infra)


class BuildStepsTest(testing.AppengineTestCase):

  @mock.patch('model.BuildSteps.MAX_STEPS_LEN', 1000)
  def test_large(self):
    container = build_pb2.Build(steps=[dict(name='x' * 1000)])
    entity = model.BuildSteps()
    entity.write_steps(container)
    self.assertTrue(entity.step_container_bytes_zipped)
    entity.put()

    entity = entity.key.get()
    actual = build_pb2.Build()
    entity.read_steps(actual)
    self.assertEqual(actual, container)

  @ndb.transactional
  def cancel_incomplete_steps(self, build_id, end_ts):
    model.BuildSteps.cancel_incomplete_steps_async(
        build_id,
        end_ts,
    ).get_result()

  def test_cancel_incomplete(self):
    steps = model.BuildSteps.make(
        build_pb2.Build(
            id=123,
            steps=[
                dict(
                    name='a',
                    status=common_pb2.SUCCESS,
                ),
                dict(
                    name='b',
                    status=common_pb2.STARTED,
                    summary_markdown='running',
                    start_time=dict(seconds=123),
                ),
            ],
        )
    )
    steps.put()

    end_ts = timestamp_pb2.Timestamp(seconds=12345)
    self.cancel_incomplete_steps(123, end_ts)

    steps = steps.key.get()
    step_container = build_pb2.Build()
    steps.read_steps(step_container)
    self.assertEqual(step_container.steps[0].status, common_pb2.SUCCESS)
    self.assertEqual(step_container.steps[1].status, common_pb2.CANCELED)
    self.assertEqual(step_container.steps[1].end_time, end_ts)
    self.assertEqual(
        step_container.steps[1].summary_markdown,
        'running\nstep was canceled because it did not end before build ended'
    )

  def test_cancel_incomplete_no_entity(self):
    end_ts = timestamp_pb2.Timestamp(seconds=12345)
    self.cancel_incomplete_steps(123, end_ts)
