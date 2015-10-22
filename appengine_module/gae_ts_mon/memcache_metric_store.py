# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import functools
import logging
import operator
import threading

from google.appengine.api import memcache
from google.appengine.ext import ndb

from infra_libs.ts_mon.common import errors
from infra_libs.ts_mon.common import metric_store


class MetricIndexEntry(ndb.Model):
  name = ndb.StringProperty()
  job_name = ndb.StringProperty()
  metric = ndb.PickleProperty()
  registered = ndb.DateTimeProperty(auto_now=True)


class MemcacheMetricStore(metric_store.MetricStore):
  """A metric store that keeps values in App Engine's memcache."""

  CAS_RETRIES = 10
  BASE_NAMESPACE = 'ts_mon_py'

  def __init__(self, state, time_fn=None):
    super(MemcacheMetricStore, self).__init__(state, time_fn=time_fn)

    self._thread_local = threading.local()
    self.update_metric_index()

  def _namespace_for_job(self, job_name=None):
    if job_name is None:
      job_name = self._state.target.job_name
    return '%s_%s' % (self.BASE_NAMESPACE, job_name)

  def _target_key(self):
    return (self._state.target.hostname, self._state.target.task_num)

  def _client(self):
    """Returns a google.appengine.api.memcache.Client.

    A different memcache client will be returned for each thread.
    """
    try:
      return self._thread_local.client
    except AttributeError:
      self._thread_local.client = memcache.Client()
      return self._thread_local.client

  def update_metric_index(self):
    entities = [
        MetricIndexEntry(
            id='%s/%s' % (self._state.target.job_name, name),
            name=name,
            job_name=self._state.target.job_name,
            metric=metric)
        for name, metric in self._state.metrics.iteritems()]
    ndb.put_multi(entities)

  def get(self, name, fields, default=None):
    entry = self._client().get(name, namespace=self._namespace_for_job())
    if entry is None:
      return default

    _, targets_values = entry

    return targets_values.get(self._target_key(), {}).get(fields, default)

  def get_all(self):
    client = self._client()
    target = copy.copy(self._state.target)

    # Fetch the metric index from datastore.
    entities = collections.defaultdict(dict)
    for entity in MetricIndexEntry.query():
      entities[entity.job_name][entity.name] = entity

    for job_name, entities in entities.iteritems():
      target.job_name = job_name

      # Fetch all the keys in this namespace.
      values = self._client().get_multi(
          entities.keys(), namespace=self._namespace_for_job(job_name))

      for name, (start_time, targets_values) in values.iteritems():
        for (hostname, task_num), fields_values in targets_values.iteritems():
          target.hostname = hostname
          target.task_num = task_num
          yield (copy.copy(target), entities[name].metric, start_time,
                 fields_values)

  def _compare_and_set(self, name, modify_fn, namespace):
    client = self._client()

    for _ in xrange(self.CAS_RETRIES):
      entry = client.get(name, for_cas=True, namespace=namespace)

      if entry is None:
        success = client.add(name, modify_fn(entry), namespace=namespace)
      else:
        success = client.cas(name, modify_fn(entry), namespace=namespace)

      if success:
        return
    else:
      logging.warning(
          'Memcache compare-and-set failed %d times for key %s in namespace %s',
          self.CAS_RETRIES, name, namespace)

  def _compare_and_set_metric(self, name, fields, modify_value_fn, delta):
    def modify_fn(entry):
      if entry is None:
        entry = (self._start_time(name), {})

      _, targets = entry

      target_key = self._target_key()
      if target_key not in targets:
        targets[target_key] = {}
      values = targets[target_key]

      values[fields] = modify_value_fn(values.get(fields, 0), delta)

      return entry
    self._compare_and_set(name, modify_fn, self._namespace_for_job())

  def set(self, name, fields, value, enforce_ge=False):
    def modify_fn(old_value, _delta):
      if enforce_ge and old_value is not None and value < old_value:
        raise errors.MonitoringDecreasingValueError(name, old_value, value)
      return value

    self._compare_and_set_metric(name, fields, modify_fn, None)

  def incr(self, name, fields, delta, modify_fn=operator.add):
    if delta < 0:
      raise errors.MonitoringDecreasingValueError(name, None, delta)

    self._compare_and_set_metric(name, fields, modify_fn, delta)

  def reset_for_unittest(self, name=None):
    if name is None:
      self._client().delete_multi(self._state.metrics.keys(),
                                  namespace=self._namespace_for_job())
    else:
      self._client().delete(name, namespace=self._namespace_for_job())
