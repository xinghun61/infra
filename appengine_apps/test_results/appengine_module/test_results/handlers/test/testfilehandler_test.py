# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json

from appengine_module.testing_utils import testing

from appengine_module.test_results import main
from appengine_module.test_results.handlers import master_config
from appengine_module.test_results.handlers import testfilehandler
from appengine_module.test_results.model.jsonresults import (
  JSON_RESULTS_HIERARCHICAL_VERSION
)


class TestFileHandlerTest(testing.AppengineTestCase):

  app_module = main.app

  def test_basic_upload(self):
    master = master_config.getMaster('chromium.chromiumos')
    builder = 'test-builder'
    test_type = 'test-type'
    test_data = {
        'tests': {
            'Test1.testproc1': {
                'expected': 'PASS',
                'actual': 'FAIL',
                'time': 1,
            }
        },
        'build_number': '123',
        'version': JSON_RESULTS_HIERARCHICAL_VERSION,
        'builder_name': builder,
        'blink_revision': '12345',
        'seconds_since_epoch': 1406123456,
        'num_failures_by_type': {
            'FAIL': 0,
            'SKIP': 0,
            'PASS': 1
        },
        'chromium_revision': '67890',
    }

    params = collections.OrderedDict([
        (testfilehandler.PARAM_BUILDER, builder),
        (testfilehandler.PARAM_MASTER, master['url_name']),
        (testfilehandler.PARAM_TEST_TYPE, test_type),
    ])
    upload_files = [
        ('file', 'full_results.json', json.JSONEncoder().encode(test_data))]
    response = self.test_app.post(
        '/testfile/upload', params=params, upload_files=upload_files)
    self.assertEqual(response.status_int, 200)

    # test aggregated results.json got generated
    params = collections.OrderedDict([
        (testfilehandler.PARAM_BUILDER, builder),
        (testfilehandler.PARAM_MASTER, master['url_name']),
        (testfilehandler.PARAM_TEST_TYPE, test_type),
        (testfilehandler.PARAM_NAME, 'results.json')
    ])
    response = self.test_app.get('/testfile', params=params)
    self.assertEqual(response.status_int, 200)
    response_json = json.loads(response.normal_body)
    self.assertEqual(response_json[builder]['tests']['Test1.testproc1'],
                     {'results': [[1, 'Q']], 'times': [[1, 1]]})

    # test testlistjson=1
    params[testfilehandler.PARAM_TEST_LIST_JSON] = '1'

    response = self.test_app.get('/testfile', params=params)
    self.assertEqual(response.status_int, 200)
    response_json = json.loads(response.normal_body)
    self.assertEqual(response_json[builder]['tests']['Test1.testproc1'], {})

  def test_get_nonexistant_results(self):
    master = master_config.getMaster('chromium.chromiumos')
    builder = 'test-builder'
    test_type = 'test-type'

    params = collections.OrderedDict([
        (testfilehandler.PARAM_BUILDER, builder),
        (testfilehandler.PARAM_MASTER, master['url_name']),
        (testfilehandler.PARAM_TEST_TYPE, test_type),
        (testfilehandler.PARAM_NAME, 'results.json')
    ])
    self.test_app.get('/testfile', params=params, status=404)

    params[testfilehandler.PARAM_TEST_LIST_JSON] = '1'
    self.test_app.get('/testfile', params=params, status=404)

  def test_deprecated_master_name(self):
    """Verify that a file uploaded with a deprecated master name
    can be downloaded by the corresponding new-style master name.
    """
    master = master_config.getMaster('chromium.chromiumos')
    builder = 'test-builder'
    test_type = 'test-type'
    test_data = {
        'tests': {
            'Test1.testproc1': {
                'expected': 'PASS',
                'actual': 'PASS',
                'time': 1,
            }
        },
        'build_number': '123',
        'version': JSON_RESULTS_HIERARCHICAL_VERSION,
        'builder_name': builder,
        'blink_revision': '12345',
        'seconds_since_epoch': 1406123456,
        'num_failures_by_type': {
            'FAIL': 0,
            'SKIP': 0,
            'PASS': 1
        },
        'chromium_revision': '67890',
    }

    # Upload file using deprecated master name.
    params = collections.OrderedDict([
        (testfilehandler.PARAM_BUILDER, builder),
        (testfilehandler.PARAM_MASTER, master['name']),
        (testfilehandler.PARAM_TEST_TYPE, test_type),
    ])
    upload_files = [
        ('file', 'full_results.json', json.JSONEncoder().encode(test_data))]
    response = self.test_app.post(
        '/testfile/upload', params=params, upload_files=upload_files)
    self.assertEqual(response.status_int, 200)

    # Download file using deprecated master name.
    params = collections.OrderedDict([
        (testfilehandler.PARAM_BUILDER, builder),
        (testfilehandler.PARAM_MASTER, master['name']),
        (testfilehandler.PARAM_TEST_TYPE, test_type),
        (testfilehandler.PARAM_BUILD_NUMBER, '123'),
        (testfilehandler.PARAM_NAME, 'full_results.json')
    ])
    response = self.test_app.get('/testfile', params=params)
    self.assertEqual(response.status_int, 200)
    response_json = json.loads(response.normal_body)
    self.assertEqual(response_json['chromium_revision'], '67890')

    # Download file using new-style name.
    params = collections.OrderedDict([
        (testfilehandler.PARAM_BUILDER, builder),
        (testfilehandler.PARAM_MASTER, master['url_name']),
        (testfilehandler.PARAM_TEST_TYPE, test_type),
        (testfilehandler.PARAM_BUILD_NUMBER, '123'),
        (testfilehandler.PARAM_NAME, 'full_results.json')
    ])
    response = self.test_app.get('/testfile', params=params)
    self.assertEqual(response.status_int, 200)
    response_json = json.loads(response.normal_body)
    self.assertEqual(response_json['chromium_revision'], '67890')
