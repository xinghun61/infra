# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes representing the monitoring interface for tasks or devices."""


class Target(object):
  """Abstract base class for a monitoring target.

  A Target is a "thing" that should be monitored, for example, a device or a
  process. The majority of the time, a single process will have only a single
  Target.

  Do not directly instantiate an object of this class.
  Use the concrete child classes instead:
  * DeviceTarget to monitor a host machine that may be running a task;
  * TaskTarget to monitor a job or tasks running in (potentially) many places.
  """

  def __init__(self):
    # Subclasses should list the updatable target fields here.
    self._fields = tuple()

  def populate_target_pb(self, collection):
    """Populate the 'target' into a MetricsCollection."""
    raise NotImplementedError()

  def update(self, target_fields):
    """Update target fields from a dict."""
    for name, value in target_fields.iteritems():
      if name not in self._fields:
        raise AttributeError('Bad target field: %s' % name)
      # Make sure the attribute actually exists in the object.
      getattr(self, name)
      setattr(self, name, value)

  def to_dict(self):
    """Return target fields as a dict."""
    return {name: getattr(self, name) for name in self._fields}

  def __eq__(self, other):
    # pylint: disable=unidiomatic-typecheck
    return (type(self) == type(other) and
            self._fields == other._fields and
            all(getattr(self, name) == getattr(other, name)
                for name in self._fields))

  def __hash__(self):
    return hash(tuple(getattr(self, name) for name in self._fields))


class DeviceTarget(Target):
  """Monitoring interface class for monitoring specific hosts or devices."""

  def __init__(self, region, role, network, hostname):
    """Create a Target object exporting info about a specific device.

    Args:
      region (str): physical region in which the device is located.
      role (str): role of the device.
      network (str): virtual network on which the device is located.
      hostname (str): name by which the device self-identifies.
    """
    super(DeviceTarget, self).__init__()
    self.region = region
    self.role = role
    self.network = network
    self.hostname = hostname
    self.realm = 'ACQ_CHROME'
    self.alertable = True
    self._fields = ('region', 'role', 'network', 'hostname')

  def populate_target_pb(self, collection):
    """Populate the 'network_device' target into metrics_pb2.MetricsCollection.

    Args:
      collection (metrics_pb2.MetricsCollection): the collection proto to be
          populated.
    """
    collection.network_device.metro = self.region
    collection.network_device.role = self.role
    collection.network_device.hostgroup = self.network
    collection.network_device.hostname = self.hostname
    collection.network_device.realm = self.realm
    collection.network_device.alertable = self.alertable


class TaskTarget(Target):
  """Monitoring interface class for monitoring active jobs or processes."""

  def __init__(self, service_name, job_name, region, hostname, task_num=0):
    """Create a Target object exporting info about a specific task.

    Args:
      service_name (str): service of which this task is a part.
      job_name (str): specific name of this task.
      region (str): general region in which this task is running.
      hostname (str): specific machine on which this task is running.
      task_num (int): replication id of this task.
    """
    super(TaskTarget, self).__init__()
    self.service_name = service_name
    self.job_name = job_name
    self.region = region
    self.hostname = hostname
    self.task_num = task_num
    self._fields = ('service_name', 'job_name', 'region',
                    'hostname', 'task_num')

  def populate_target_pb(self, collection):
    """Populate the 'task' target into metrics_pb2.MetricsCollection.

    Args:
      collection (metrics_pb2.MetricsCollection): the collection proto to be
          populated.
    """
    collection.task.service_name = self.service_name
    collection.task.job_name = self.job_name
    collection.task.data_center = self.region
    collection.task.host_name = self.hostname
    collection.task.task_num = self.task_num
