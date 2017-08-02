# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import json
import unittest

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from common import snippets
from mock import patch

import cloudstorage


SAMPLE_FILE = {
  'all_tests':['test'],
  'per_iteration_data': [{
      'test':[{
          'output_snippet' : '[RUN] test: pass [1:2:3/4.5:WARN:m] : () [] ='
      }],
    }],
}


class GetOutputSnippetTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_app_identity_stub()
    self.testbed.init_blobstore_stub()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_urlfetch_stub()
    cloudstorage.set_default_retry_params(None)
    super(GetOutputSnippetTest, self).setUp()

  def tearDown(self):
    self.testbed.deactivate()
    super(GetOutputSnippetTest, self).tearDown()

  def test_get_json_file(self):
    f = cloudstorage.open('/bucket/testfile', 'w')
    f.write(json.dumps(SAMPLE_FILE))
    f.close()
    json_file = snippets.get_json_file('/bucket/testfile')
    self.assertEqual(json_file, SAMPLE_FILE)

  def test_get_json_file_with_improper_formatted_json_file(self):
    f = cloudstorage.open('/bucket/testfile', 'w')
    f.write(' { { ] { } bad json ] ] { }}} ')
    f.close()
    json_file = snippets.get_json_file('/bucket/testfile')
    self.assertEqual(json_file, None)

  def test_get_json_file_when_file_does_not_exist(self):
    json_file = snippets.get_json_file('/bucket/testfile')
    self.assertEqual(json_file, None)

  def test_get_raw_output_sample_json(self):
    snippet = snippets.get_raw_output_snippet(SAMPLE_FILE, 'test')
    self.assertEqual(snippet, "[RUN] test: pass [1:2:3/4.5:WARN:m] : () [] =")

  def test_fail_get_raw_output_given_empty_json(self):
    snippet = snippets.get_raw_output_snippet({}, 'test')
    self.assertEqual(snippet, None)

  def test_fail_get_raw_output_test_not_in_json(self):
    snippet = snippets.get_raw_output_snippet(
        SAMPLE_FILE, 'test_not_there')
    self.assertEqual(snippet, None)

  def test_process_snippet(self):
    snippet = snippets.process_snippet(
        "[RUN] test: pass [1:2:3/4.5:WARN:m] : () [] =")
    self.assertEqual(snippet, ["RUN", "test", "pass", "WARN", "m"])

  @patch.object(snippets, 'get_json_file')
  def test_get_processed_output_batch_from_sample_json(self, mock_json_file):
    mock_json_file.return_value = SAMPLE_FILE
    cleaned_snippets = snippets.get_processed_output_snippet_batch(
        'test_master', 'test_builder', 1234,'test_step', ['test'])
    self.assertDictEqual(
        cleaned_snippets, {'test' : ["RUN", "test", "pass", "WARN", "m"]})

  @patch.object(snippets, 'get_json_file')
  def test_get_processed_output_batch_tests_not_in_file(self, mock_json_file):
    mock_json_file.return_value = SAMPLE_FILE
    cleaned_snippets = snippets.get_processed_output_snippet_batch(
        'test_master', 'test_builder', 1234, 'test_step', ['test_not_there'])
    self.assertEqual(cleaned_snippets, {})

  @patch.object(snippets, 'get_json_file')
  def test_get_processed_output_batch_from_empty_json(self, mock_json_file):
    mock_json_file.return_value = None
    cleaned_snippets = snippets.get_processed_output_snippet_batch(
        'test_master', 'test_builder', 1234, 'test_step', ['test_not_there'])
    self.assertEqual(cleaned_snippets, {})
