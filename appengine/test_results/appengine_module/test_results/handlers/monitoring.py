# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import webapp2

from google.appengine.api import taskqueue

from appengine_module.test_results.handlers import util
from infra_libs import ts_mon
from infra_libs import event_mon


class EventMonUploader(webapp2.RequestHandler):
  num_tests = ts_mon.CounterMetric(
      'test_results/num_tests',
      description='Number of tests in the test results')
  num_characters = ts_mon.CounterMetric(
      'test_results/num_characters',
      description='Sum of all characters in all test names')

  def post(self):
    # TODO(sergiyb): Retrieve test json from datastore based on task parameters.
    # TODO(sergiyb): Create a proto event and send it to event_mon.
    pass

  @classmethod
  def upload(cls, master, builder, build_number, test_type, file_json):
    taskqueue.add(url='/internal/monitoring/upload', params={
      'master': master,
      'builder': builder,
      'build_number': build_number,
      'test_type': test_type,
    })

    # Since the task queue doesn't actually do anything yet, we currently just
    # report stats about number of tests and characters to ts_mon to estimate
    # size of the data that we are going to report to event_mon.
    # TODO(sergiyb): Remove this code and file_json parameter once we get needed
    # estimates.
    try:
      tests = util.flatten_tests_trie(
          file_json.get('tests', {}), file_json.get('path_delimieter', '/'))
      cls.num_tests.increment_by(len(tests))
      cls.num_characters.increment_by(sum(len(t) for t in tests))
    except Exception:
      logging.exception('Failed to parse test results %s', file_json)
      return
