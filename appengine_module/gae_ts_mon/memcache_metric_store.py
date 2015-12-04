# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import functools
import logging
import operator
import random
import threading

from google.appengine.api import memcache
from google.appengine.api import modules
from google.appengine.ext import ndb

from infra_libs.ts_mon.common import errors
from infra_libs.ts_mon.common import metric_store
from infra_libs.ts_mon.common import metrics


# Note: this metric is not registered in the index, since it's handled in
# a special way.
appengine_default_version = metrics.StringMetric(
    'appengine/default_version',
    description='Name of the version currently marked as default.')


class MetricIndexEntry(ndb.Model):
  name = ndb.StringProperty()
  job_name = ndb.StringProperty()
  metric = ndb.PickleProperty()
  registered = ndb.DateTimeProperty(auto_now=True)


class MemcacheMetricStore(metric_store.MetricStore):
  """A metric store that keeps values in App Engine's memcache."""

  CAS_RETRIES = 10
  BASE_NAMESPACE = 'ts_mon_py'
  SHARDS_PER_METRIC = 10

  METRICS_EXCLUDED_FROM_INDEX = (appengine_default_version,)

  def __init__(self, state, time_fn=None, report_module_versions=False):
    super(MemcacheMetricStore, self).__init__(state, time_fn=time_fn)

    self.report_module_versions = report_module_versions

    self._thread_local = threading.local()
    self.update_metric_index()

  def _namespace_for_job(self, job_name=None):
    if job_name is None:
      job_name = self._state.target.job_name
    return '%s_%s' % (self.BASE_NAMESPACE, job_name)

  def _target_key(self):
    return self._state.target.hostname

  def _client(self):
    """Returns a google.appengine.api.memcache.Client.

    A different memcache client will be returned for each thread.
    """
    try:
      return self._thread_local.client
    except AttributeError:
      self._thread_local.client = memcache.Client()
      return self._thread_local.client

  def _is_metric_sharded(self, metric):
    if isinstance(metric, (metrics.CounterMetric, metrics.CumulativeMetric)):
      return True
    if isinstance(metric, metrics.DistributionMetric) and metric.is_cumulative:
      return True
    return False

  def _random_shard(self, metric, select_shard=random.randint):
    if not self._is_metric_sharded(metric):
      return metric.name
    return '%s-%d' % (metric.name, select_shard(1, self.SHARDS_PER_METRIC))

  def _all_shards(self, metric):
    if not self._is_metric_sharded(metric):
      return [metric.name]
    return [
        '%s-%d' % (metric.name, shard)
        for shard in xrange(1, self.SHARDS_PER_METRIC + 1)]

  def update_metric_index(self):
    entities = [
        MetricIndexEntry(
            id='%s/%s' % (self._state.target.job_name, name),
            name=name,
            job_name=self._state.target.job_name,
            metric=metric)
        for name, metric in self._state.metrics.iteritems()
        if metric not in self.METRICS_EXCLUDED_FROM_INDEX]
    ndb.put_multi(entities)

  def get(self, name, fields, default=None):
    if name not in self._state.metrics:
      return default

    keys = self._all_shards(self._state.metrics[name])
    entries = self._client().get_multi([(None, x) for x in keys],
                                       namespace=self._namespace_for_job())
    values = []
    for entry in entries.values():
      _, targets_values = entry
      values.append(targets_values.get(self._target_key(), {})
                                  .get(fields, default))

    if not values:
      return default
    if len(values) == 1:
      return values[0]
    if not all(isinstance(x, (int, float)) for x in values):
      raise TypeError(
          'get() is not supported on sharded cumulative distribution metrics')
    return sum(values)

  def get_all(self):
    if self.report_module_versions:
      for module_name in modules.get_modules():
        # 'hostname' is usually set to module version name, but default version
        # name is a global thing, not associated with any version.
        target = copy.copy(self._state.target)
        target.hostname = ''
        target.job_name = module_name
        fields_values = {
            appengine_default_version._normalize_fields(None):
                modules.get_default_version(module_name),
        }
        yield (target, appengine_default_version, 0, fields_values)

    client = self._client()
    target = copy.copy(self._state.target)

    # Fetch the metric index from datastore.
    all_entities = collections.defaultdict(dict)
    for entity in MetricIndexEntry.query():
      all_entities[entity.job_name][entity.name] = entity

    for job_name, entities in all_entities.iteritems():
      target.job_name = job_name

      # Create the list of keys to fetch.  Sharded metrics (counters) are
      # spread across multiple keys in memcache.
      keys = []
      shard_map = {}  # key -> (index, metric name)
      for name, entity in entities.iteritems():
        if self._is_metric_sharded(entity.metric):
          for i, sharded_key in enumerate(self._all_shards(entity.metric)):
            keys.append(sharded_key)
            shard_map[sharded_key] = (i, name)
        else:
          keys.append(name)

      # Fetch all the keys in this namespace.
      values = self._client().get_multi(
          keys, namespace=self._namespace_for_job(job_name))

      for key, (start_time, targets_values) in values.iteritems():
        for hostname, fields_values in targets_values.iteritems():
          target.hostname = hostname
          if key in shard_map:
            # This row is one shard of a sharded metric - put the shard number
            # in the task number.
            target.task_num, metric_name = shard_map[key]
          else:
            target.task_num, metric_name = 0, key

          yield (copy.copy(target), entities[metric_name].metric, start_time,
                 fields_values)

  def _compare_and_set(self, metric, modify_fn, namespace):
    client = self._client()

    for _ in xrange(self.CAS_RETRIES):
      # Pick one of the shards to modify.
      name = self._random_shard(metric)

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
    if any(name == m.name for m in self.METRICS_EXCLUDED_FROM_INDEX):
      raise errors.MonitoringError('Metric %s is magical, can\'t set it' % name)

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
    self._compare_and_set(
        self._state.metrics[name], modify_fn, self._namespace_for_job())

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
