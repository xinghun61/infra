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

  # String representaiton of int.
  io_timeout_secs = basestring


class SwarmingTaskRequest(StructuredObject):
  """Represents a task request on Swarming server."""

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
        created_ts=None,
        expiration_secs='3600',
        name='',
        parent_task_id='',
        priority='150',
        properties=SwarmingTaskProperties(
            caches=[],
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

  @classmethod
  def FromSerializable(cls, data):
    """Deserializes the given data into a SwarmingTaskRequest.

      Because Swarming frequently adds new fields to task requests, maintaining
      a strict 1:1 mapping between Findit and Swarming is not feasible. Instead
      when deserializing a swarming task request, only consider the fields that
      are necessary.

    Args:
      data (dict): The dict mapping from defined attributes to their values.

    Returns:
      An instance of the given class with attributes set to the given data.
    """
    properties = data.get('properties', {})
    inputs_ref = properties.get('inputs_ref', {})

    return SwarmingTaskRequest(
        created_ts=data.get('created_ts'),
        expiration_secs=str(data.get('expiration_secs')),
        name=data.get('name'),
        parent_task_id=data.get('parent_task_id'),
        priority=str(data.get('priority')),
        properties=SwarmingTaskProperties(
            caches=properties.get('caches'),
            command=properties.get('command'),
            dimensions=properties.get('dimensions'),
            env=properties.get('env'),
            env_prefixes=properties.get('env_prefixes'),
            execution_timeout_secs=str(
                properties.get('execution_timeout_secs')),
            extra_args=ListOfBasestring.FromSerializable(
                properties.get('extra_args')),
            grace_period_secs=str(properties.get('grace_period_secs')),
            io_timeout_secs=str(properties.get('io_timeout_secs')),
            idempotent=properties.get('idempotent'),
            inputs_ref=SwarmingTaskInputsRef(
                isolated=inputs_ref.get('isolated'),
                isolatedserver=inputs_ref.get('isolatedserver'),
                namespace=inputs_ref.get('namespace'))),
        pubsub_auth_token=data.get('pubsub_auth_token'),
        pubsub_topic=data.get('pubsub_topic'),
        pubsub_userdata=data.get('pubsub_userdata'),
        service_account=data.get('service_account'),
        tags=ListOfBasestring.FromSerializable(data.get('tags')),
        user=data.get('user'))
