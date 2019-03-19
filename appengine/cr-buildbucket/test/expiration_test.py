# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb

from components import auth
from components import utils
from testing_utils import testing

from test import test_util
from test.test_util import future
from proto import common_pb2
import expiration
import model


class ExpireBuildTests(testing.AppengineTestCase):

  def setUp(self):
    super(ExpireBuildTests, self).setUp()
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)
    self.patch('tq.enqueue_async', autospec=True, return_value=future(None))

  def test_reschedule_builds_with_expired_leases(self):
    build = test_util.build()
    build.lease_expiration_date = utils.utcnow()
    build.lease_key = 1
    build.leasee = auth.Anonymous
    build.put()

    expiration.expire_build_leases()
    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.SCHEDULED)
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.leasee)

  def test_completed_builds_are_not_reset(self):
    build = test_util.build(status=common_pb2.SUCCESS)
    build.put()
    expiration.expire_build_leases()
    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.SUCCESS)

  def test_expire_builds(self):
    build_time = utils.utcnow() - datetime.timedelta(days=365)
    build = test_util.build(create_time=test_util.dt2ts(build_time))
    build.put()

    expiration.expire_builds()
    build = build.key.get()
    self.assertEqual(build.proto.status, common_pb2.INFRA_FAILURE)
    self.assertTrue(build.proto.infra_failure_reason.resource_exhaustion)
    self.assertIsNone(build.lease_key)

  def test_delete_builds(self):
    old_build_time = utils.utcnow() - model.BUILD_STORAGE_DURATION * 2
    old_build = test_util.build(create_time=test_util.dt2ts(old_build_time))
    old_build_steps = model.BuildSteps(
        key=model.BuildSteps.key_for(old_build.key),
        step_container_bytes='',
    )

    new_build_time = utils.utcnow() - model.BUILD_STORAGE_DURATION / 2
    new_build = test_util.build(create_time=test_util.dt2ts(new_build_time))

    ndb.put_multi([old_build, old_build_steps, new_build])

    expiration.delete_builds()
    self.assertIsNone(old_build.key.get())
    self.assertIsNone(old_build_steps.key.get())
    self.assertIsNotNone(new_build.key.get())
