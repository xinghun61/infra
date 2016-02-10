# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class SwarmingTaskRequest(object):  # pragma: no cover. Tested indirectly.
  """Represents a task request on Swarming server."""

  def __init__(self):
    self.expiration_secs = 3600
    self.name = ''
    self.parent_task_id = ''
    # Set as lowest priority. Note: The higher value, the lower priority.
    self.priority = 150
    self.tags = []
    self.user = ''

    # Settings in task properties.
    self.command = None
    self.dimensions = []
    self.env = []
    self.execution_timeout_secs = 3600
    self.extra_args = []
    self.grace_period_secs = 30
    self.idempotent = True
    self.inputs_ref = {}
    self.io_timeout_secs = 1200

  def Serialize(self):
    """Serializes and returns a dict representing the Swarming task request."""
    return {
        'expiration_secs': self.expiration_secs,
        'name': self.name,
        'parent_task_id': self.parent_task_id,
        'priority': self.priority,
        'properties': {
            'command': self.command,
            'dimensions': self.dimensions,
            'env': self.env,
            'execution_timeout_secs': self.execution_timeout_secs,
            'extra_args': self.extra_args,
            'grace_period_secs': self.grace_period_secs,
            'idempotent': self.idempotent,
            'inputs_ref': self.inputs_ref,
            'io_timeout_secs': self.io_timeout_secs,
        },
        'tags': self.tags,
        'user': self.user,
    }

  @staticmethod
  def Deserialize(data):
    """Deserializes and returns a Swarming task request from the given data.

    Args:
      data (dict): A serialized dict representing a Swarming task request.
    """
    task_request = SwarmingTaskRequest()

    task_request.expiration_secs = data['expiration_secs']
    task_request.name = data['name']
    task_request.parent_task_id = data.get('parent_task_id')
    task_request.priority = data['priority']
    task_request.tags = data['tags'] or []
    task_request.user = data.get('user')

    task_request.command = data['properties'].get('command')
    task_request.dimensions = data['properties']['dimensions']
    task_request.env = data['properties']['env'] or []
    task_request.execution_timeout_secs = data[
        'properties']['execution_timeout_secs']
    task_request.grace_period_secs = data['properties']['grace_period_secs']
    task_request.extra_args = data['properties']['extra_args'] or []
    task_request.idempotent = data['properties']['idempotent']
    task_request.inputs_ref = data['properties']['inputs_ref']
    task_request.io_timeout_secs = data['properties']['io_timeout_secs']

    return task_request
