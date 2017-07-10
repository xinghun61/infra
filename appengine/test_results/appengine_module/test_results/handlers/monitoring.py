# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import webapp2

from google.appengine.ext import db
from google.appengine.api import taskqueue

from appengine_module.test_results.handlers import util
from appengine_module.test_results.model.jsonresults import JsonResults
from appengine_module.test_results.model.testfile import TestFile
from appengine_module.test_results.model.testlocation import TestLocation
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

  @staticmethod
  def _filter_new_locations(locations):
    test_names = locations.keys()
    loc_entities = TestLocation.get_by_key_name(test_names)
    new_locations = {}
    for i, loc_entity in enumerate(loc_entities):
      test_name = test_names[i]
      location = locations[test_name]
      if (loc_entity is None or loc_entity.file != location.get('file') or
          loc_entity.line != location.get('line')):
        new_locations[test_name] = location
        # We don't want to block on put operations and should some of them fail,
        # we'll just end up reporting some locations a few times, which is
        # acceptable unless it starts to happen to frequently. See
        # https://crbug.com/740554 for more details.
        db.put_async(TestLocation(key_name=test_name, file=location.get('file'),
                                  line=location.get('line')))

        # Limit number of reported test locations to avoid exceeding 10MiB
        # request limit on the event_mon endpoint. The missing test locations
        # will be still reported when these tests are run again. Eventually the
        # number of new locations will decrease sufficiently that this check
        # will be rarely used and thus all test locations will be reported
        # promptly.
        if len(new_locations) >= 1000:
          logging.warn('Ignoring new locations to avoid exceeding request size')
          break

    return new_locations

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
    step_name = payload.get('step_name')
    if (not master or not builder or build_number is None or not test_type or
        not step_name):
      logging.error(
          'Missing required parameters: (master=%s, builder=%s, '
          'build_number=%s, test_type=%s, step_name=%s)' %
          (master, builder, build_number, test_type, step_name))
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
    test_results.step_name = step_name
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

    test_locations = event.proto.test_locations_event
    test_locations.bucket_name = master
    test_locations.builder_name = builder
    test_locations.build_number = int(build_number)
    test_locations.step_name = step_name
    if 'seconds_since_epoch' in file_json:
      test_locations.usec_since_epoch = long(
          float(file_json['seconds_since_epoch']) * 1000 * 1000)

    test_locs_json = file_json.get('test_locations') or {}
    test_locs_json = self._filter_new_locations(test_locs_json)
    for name, loc in test_locs_json.iteritems():
      location = test_locations.locations.add()
      location.test_name = name
      location.file = loc['file']
      location.line = int(loc['line'])

    event.send()
