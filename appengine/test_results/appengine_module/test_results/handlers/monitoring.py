# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import webapp2

from google.appengine.api import taskqueue

from appengine_module.test_results.handlers import util
from appengine_module.test_results.model.jsonresults import JsonResults
from appengine_module.test_results.model.testfile import TestFile
from infra_libs import ts_mon
from infra_libs import event_mon


class EventMonUploader(webapp2.RequestHandler):
  num_test_results = ts_mon.CounterMetric(
      'test_results/num_test_results',
      'Number of reported test results',
      [ts_mon.StringField('result_type'),
       ts_mon.StringField('master'),
       ts_mon.StringField('builder'),
       ts_mon.StringField('test_type')])

  def post(self):
    if not self.request.body:
      logging.error('Missing request payload')
      self.response.set_status(400)
      return

    try:
      payload = json.loads(self.request.body)
    except ValueError:
      logging.error('Failed to parse request payload as JSON')
      self.response.set_status(400)
      return

    # Retrieve test json from datastore based on task parameters.
    master = payload.get('master')
    builder = payload.get('builder')
    build_number = payload.get('build_number')
    test_type = payload.get('test_type')
    if not master or not builder or build_number is None or not test_type:
      logging.error(
          'Missing required parameters: (master=%s, builder=%s, '
          'build_number=%s, test_type=%s)' %
          (master, builder, build_number, test_type))
      self.response.set_status(400)
      return

    files = TestFile.get_files(
        master, builder, test_type, build_number, 'full_results.json',
        load_data=True, limit=1)
    if not files:
      logging.error('Failed to find full_results.json for (%s, %s, %s, %s)' % (
                    master, builder, build_number, test_type))
      self.response.set_status(404)
      return
    file_json = JsonResults.load_json(files[0].data)

    # Create a proto event and send it to event_mon.
    event = event_mon.Event('POINT')
    test_results = event.proto.test_results
    test_results.master_name = master
    test_results.builder_name = builder
    test_results.build_number = int(build_number)
    test_results.test_type = test_type
    if 'interrupted' in file_json:
      test_results.interrupted = file_json['interrupted']
    if 'version' in file_json:
      test_results.version = file_json['version']
    if 'seconds_since_epoch' in file_json:
      test_results.usec_since_epoch = long(
          float(file_json['seconds_since_epoch']) * 1000 * 1000)

    def convert_test_result_type(json_val):
      self.num_test_results.increment({
          'result_type': json_val, 'master': master, 'builder': builder,
          'test_type': test_type})
      try:
        return (event_mon.protos.chrome_infra_log_pb2.TestResultsEvent.
                TestResultType.Value(json_val.upper().replace('+', '_')))
      except ValueError:
        return event_mon.protos.chrome_infra_log_pb2.TestResultsEvent.UNKNOWN

    tests = util.flatten_tests_trie(
        file_json.get('tests', {}), file_json.get('path_delimiter', '/'))
    for name, test in tests.iteritems():
      test_result = test_results.tests.add()
      test_result.test_name = name
      test_result.actual.extend(
          convert_test_result_type(res) for res in test['actual'])
      test_result.expected.extend(
          convert_test_result_type(res) for res in test['expected'])

    event.send()

  @classmethod
  def upload(cls, master, builder, build_number, test_type):
    taskqueue.add(url='/internal/monitoring/upload', params={
      'master': master,
      'builder': builder,
      'build_number': build_number,
      'test_type': test_type,
    })
