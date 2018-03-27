# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra_api_clients.swarming.swarming_task_request import (
    SwarmingTaskInputsRef)
from infra_api_clients.swarming.swarming_task_request import (
    SwarmingTaskProperties)
from infra_api_clients.swarming.swarming_task_request import SwarmingTaskRequest
from gae_libs.testcase import TestCase
from libs.list_of_basestring import ListOfBasestring


class SwarmingTaskRequestTest(TestCase):

  def testGetSwarmingTaskRequestTemplate(self):
    expected_request = SwarmingTaskRequest(
        authenticated=None,
        created_ts=None,
        expiration_secs='3600',
        name='',
        parent_task_id='',
        priority='150',
        properties=SwarmingTaskProperties(
            caches=[],
            cipd_input={},
            command=None,
            dimensions=[],
            env=None,
            env_prefixes=[],
            execution_timeout_secs='3600',
            extra_args=None,
            grace_period_secs='30',
            io_timeout_secs='1200',
            idempotent=True,
            inputs_ref=SwarmingTaskInputsRef(
                isolated=None, isolatedserver=None, namespace=None)),
        pubsub_auth_token=None,
        pubsub_topic=None,
        pubsub_userdata=None,
        service_account=None,
        tags=ListOfBasestring(),
        user='')

    self.assertEqual(expected_request,
                     SwarmingTaskRequest.GetSwarmingTaskRequestTemplate())
