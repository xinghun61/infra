# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb

from components import auth
from components import utils
from testing_utils import testing

from test.test_util import future
from proto import build_pb2
import expiration
import model


class ExpireBuildTests(testing.AppengineTestCase):

  def setUp(self):
    super(ExpireBuildTests, self).setUp()
    self.now = datetime.datetime(2015, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

    self.patch(
        'notifications.enqueue_tasks_async',
        autospec=True,
        return_value=future(None)
    )
    self.patch(
        'bq.enqueue_pull_task_async', autospec=True, return_value=future(None)
    )

  def test_reschedule_builds_with_expired_leases(self):
    build = model.Build(
        id=model.create_build_ids(utils.utcnow(), 1)[0],
        bucket_id='chromium/try',
        create_time=utils.utcnow(),
        lease_expiration_date=utils.utcnow(),
        lease_key=1,
        leasee=auth.Anonymous,
    )
    build.put()

    expiration.expire_build_leases()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.SCHEDULED)
    self.assertIsNone(build.lease_key)
    self.assertIsNone(build.leasee)

  def test_completed_builds_are_not_reset(self):
    build = model.Build(
        id=model.create_build_ids(utils.utcnow(), 1)[0],
        bucket_id='chromium/try',
        create_time=utils.utcnow(),
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        complete_time=utils.utcnow(),
    )
    build.put()
    expiration.expire_build_leases()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)

  def test_expire_builds(self):
    build_time = utils.utcnow() - datetime.timedelta(days=365)
    build = model.Build(
        id=model.create_build_ids(build_time, 1)[0],
        bucket_id='chromium/try',
        create_time=build_time,
    )
    build.put()

    expiration.expire_builds()
    build = build.key.get()
    self.assertEqual(build.status, model.BuildStatus.COMPLETED)
    self.assertEqual(build.result, model.BuildResult.CANCELED)
    self.assertEqual(build.cancelation_reason, model.CancelationReason.TIMEOUT)
    self.assertIsNone(build.lease_key)

  def test_delete_builds(self):
    old_build_time = utils.utcnow() - model.BUILD_STORAGE_DURATION * 2
    old_build = model.Build(
        id=model.create_build_ids(old_build_time, 1)[0],
        bucket_id='chromium/try',
        create_time=old_build_time,
    )
    old_build_steps = model.BuildSteps(
        key=model.BuildSteps.key_for(old_build.key),
        step_container=build_pb2.Build(),
    )

    new_build_time = utils.utcnow() - model.BUILD_STORAGE_DURATION / 2
    new_build = model.Build(
        id=model.create_build_ids(new_build_time, 1)[0],
        bucket_id='chromium/try',
        create_time=new_build_time,
    )

    ndb.put_multi([old_build, old_build_steps, new_build])

    expiration.delete_builds()
    self.assertIsNone(old_build.key.get())
    self.assertIsNone(old_build_steps.key.get())
    self.assertIsNotNone(new_build.key.get())
