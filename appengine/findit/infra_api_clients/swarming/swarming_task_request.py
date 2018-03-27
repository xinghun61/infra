# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject


class SwarmingTaskInputsRef(StructuredObject):
  """Contains information on the locations of the binaries to run against."""
  # A hash represented the ioslated input pointing to the binaries to test.
  isolated = basestring

  # The url to the server the isolated inputs reside on.
  isolatedserver = basestring

  namespace = basestring


class SwarmingTaskProperties(StructuredObject):
  """Fields populated in swarming task requests."""
  caches = list
  command = basestring
  env_prefixes = list
  cipd_input = dict
  dimensions = list
  env = list

  # The maximum amount of time the swarming task is allowed to run before being
  # terminated returned as a string representation of an int.
  execution_timeout_secs = basestring

  extra_args = ListOfBasestring

  # String representation of int.
  grace_period_secs = basestring

  idempotent = bool

  # Information pointing to the location of the test binaries.
  inputs_ref = SwarmingTaskInputsRef

  io_timeout_secs = basestring  # String representaiton of int.


class SwarmingTaskRequest(StructuredObject):
  """Represents a task request on Swarming server."""
  authenticated = basestring

  # The created timestamp according to Swarming, returned as a string
  # representation of a timestamp.
  created_ts = basestring

  # String representation of int.
  expiration_secs = basestring

  # The name of the swarming task.
  name = basestring

  parent_task_id = basestring

  # The priority of the swarming task. The lower the number, the higher the
  # priority, represented as a string.
  priority = basestring

  service_account = basestring
  tags = ListOfBasestring
  user = basestring
  properties = SwarmingTaskProperties

  # Pub/Sub parameters
  pubsub_topic = basestring
  pubsub_auth_token = basestring
  pubsub_userdata = basestring

  @staticmethod
  def GetSwarmingTaskRequestTemplate():
    """Returns a template SwarmingTaskRequest object with default values."""
    return SwarmingTaskRequest(
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
