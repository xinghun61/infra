# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import datetime
import logging
import threading

from google.appengine.api import apiproxy_stub_map, background_thread, runtime
from google.appengine.ext import db, deferred

import app

_stats = {}
_queue = collections.deque()

_lock = threading.Lock()

_processing = False

QUEUE_THRESHOLD = 1000

def flush_summaries_to_datastore():
  global _processing

  try:
    with _lock:
      if _processing:
        return
      _processing = True

    start_time = datetime.datetime.now()

    while datetime.datetime.now() - start_time < datetime.timedelta(seconds=15):
      with _lock:
        if not _queue:
          return

        # This should be non-destructive in case db transaction fails.
        key_name = _queue[0]
        stats_value = _stats[key_name]

        app.GTestSummary.get_or_insert(
            key_name=key_name,
            weekly_timestamp=stats_value['weekly_timestamp'],
            buildbot_root=stats_value['buildbot_root'],
            builder=stats_value['builder'],
            step_name=stats_value['step_name'],
            fullname=stats_value['fullname'])
        def tx_summary():
          summary = app.GTestSummary.get_by_key_name(key_name)
          for result in stats_value['results']:
            if not summary.max_run_time_ms:
              summary.max_run_time_ms = 0.0
            if not summary.run_time_ms:
              summary.run_time_ms = 0.0
            if not summary.result_count:
              summary.result_count = 0
            if not summary.crash_or_hang_count:
              summary.crash_or_hang_count = 0
            if not summary.failure_count:
              summary.failure_count = 0
            summary.max_run_time_ms = max(summary.max_run_time_ms,
                                          float(result['run_time_ms']))
            summary.run_time_ms = (
                (summary.run_time_ms * summary.result_count) +
                float(result['run_time_ms'])) / (summary.result_count + 1)
            summary.result_count += 1
            if summary.result_count >= 10:
              summary.enough_samples = True
            if result['is_crash_or_hang']:
              summary.crash_or_hang_count += 1
            if not result['is_successful']:
              summary.failure_count += 1
            summary.crash_or_hang_rate = \
                float(summary.crash_or_hang_count) / summary.result_count
            summary.failure_rate = \
                float(summary.failure_count) / summary.result_count
          summary.put()
        db.run_in_transaction(tx_summary)

        # Now that transaction has succeeded, update in-memory state.
        _queue.remove(key_name)
        del _stats[key_name]
  finally:
    with _lock:
      _processing = False


def process_gtest_results(buildbot_root,
                          builder,
                          step_name,
                          time_finished,
                          results):
  # _processing is global but we're not modifying it.
  # global _processing

  with _lock:
    logging.debug('stats before: %d' % len(_stats.keys()))
    for fullname, result in results.items():
      weekly_timestamp = (time_finished.date() -
                          datetime.timedelta(days=time_finished.weekday()))
      key_name='%s-%s-%s-%s-%s' % (buildbot_root,
                                   builder,
                                   step_name,
                                   fullname,
                                   weekly_timestamp)
      if key_name not in _stats:
        _stats[key_name] = {
          'buildbot_root': buildbot_root,
          'builder': builder,
          'step_name': step_name,
          'fullname': fullname,
          'weekly_timestamp': weekly_timestamp,
          'results': [],
        }
        _queue.append(key_name)
      _stats[key_name]['results'].append(result)

    if not _processing and len(_stats) > QUEUE_THRESHOLD:
      background_thread.start_new_background_thread(
          flush_summaries_to_datastore, [])
