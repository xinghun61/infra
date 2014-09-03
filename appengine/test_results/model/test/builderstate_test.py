# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from datetime import datetime
from testing_support import auto_stub

from appengine.path_mangler_hack import PathMangler
with PathMangler(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))):
  from appengine.test_results.model import builderstate
  from appengine.test_results.model import testfile

from google.appengine.api import memcache
from google.appengine.ext import testbed

TEST_MASTER = 'chromium.webkit'
TEST_BUILDER = 'WebKit Linux'
TEST_TEST_TYPE = 'browser_tests'

TEST_BUILDERS = {
    'masters': [{
        'tests': {
            'browser_tests': {'builders': ['WebKit Linux', 'WebKit Mac']},
            'mini_installer_test': {'builders': ['WebKit Linux', 'WebKit Mac', 'WebKit Win']},
            'layout-tests': {'builders': ['WebKit Linux', 'WebKit Win']}},
        'name': 'ChromiumWebkit',
        'url_name': 'chromium.webkit',
        'groups': ['@ToT Chromium', '@ToT Blink'],
    }]
}
TEST_BUILDERS_DATA = json.dumps(TEST_BUILDERS, separators=(',', ':'))

TEST_BUILDER_STATE = {
    'masters': [{
        'tests': {
            'browser_tests': {'builders': {'WebKit Linux': None, 'WebKit Mac': None}},
            'mini_installer_test': {'builders': {'WebKit Linux': None,
                                                 'WebKit Mac': None,
                                                 'WebKit Win': None}},
            'layout-tests': {'builders': {'WebKit Linux': None, 'WebKit Win': None}}},
        'name': 'ChromiumWebkit',
        'url_name': 'chromium.webkit',
        'groups': ['@ToT Chromium', '@ToT Blink'],
    }]
}
TEST_BUILDER_STATE_DATA = json.dumps(TEST_BUILDER_STATE, separators=(',', ':'))

TEST_FILE = [TEST_MASTER, TEST_BUILDER, TEST_TEST_TYPE, 1,
             'full_results.json',
             '{"tests":{"test.name":{"expected":"PASS","actual":"PASS"}}}']

TEST_NOW = datetime.now()


class BuilderStateTest(auto_stub.TestCase):

  def setUp(self):
    super(BuilderStateTest, self).setUp()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    super(BuilderStateTest, self).tearDown()
    self.testbed.deactivate()

  def _validate_builder_state(self, builder_state):
    for master in TEST_BUILDER_STATE['masters']:
      master_name = master['url_name']
      result_master = builderstate.BuilderState._find_master(
          builder_state, master_name)
      self.assertIsNotNone(result_master)
      self.assertEqual(
          set(master['tests'].keys()),
          set(result_master['tests'].keys()))
      for test_type, step_data in master['tests'].items():
        result_step_data = result_master['tests'][test_type]
        self.assertEqual(
            set(step_data['builders'].keys()),
            set(result_step_data['builders'].keys()))
        for builder, timestamp in result_step_data['builders'].items():
          if master_name == TEST_MASTER and builder == TEST_BUILDER and test_type == TEST_TEST_TYPE:
            self.assertEquals(TEST_NOW.isoformat(), timestamp)
          else:
            self.assertEqual(step_data['builders'][builder], timestamp)

  def test_incremental_update_no_existing_state(self):
    builderstate.BuilderState.incremental_update(
        TEST_MASTER, TEST_BUILDER, TEST_TEST_TYPE, TEST_NOW)
    self.assertIsNone(memcache.get(builderstate.MEMCACHE_KEY))

  def test_incremental_update_with_existing_state(self):
    memcache.set(builderstate.MEMCACHE_KEY, TEST_BUILDER_STATE_DATA)
    builderstate.BuilderState.incremental_update(
        TEST_MASTER, TEST_BUILDER, TEST_TEST_TYPE, TEST_NOW)
    builder_state_data = memcache.get(builderstate.MEMCACHE_KEY)
    builder_state = json.loads(builder_state_data)
    self._validate_builder_state(builder_state)

  def test_incremental_update_unknown_master(self):
    memcache.set(builderstate.MEMCACHE_KEY, TEST_BUILDER_STATE_DATA)
    builderstate.BuilderState.incremental_update(
        'UnknownMaster', TEST_BUILDER, TEST_TEST_TYPE, TEST_NOW)

    # Data should not have changed
    builder_state_data = memcache.get(builderstate.MEMCACHE_KEY)
    self.assertEquals(TEST_BUILDER_STATE_DATA, builder_state_data)

  def test_incremental_update_unknown_step(self):
    memcache.set(builderstate.MEMCACHE_KEY, TEST_BUILDER_STATE_DATA)
    builderstate.BuilderState.incremental_update(
        TEST_MASTER, TEST_BUILDER, 'unknown-test', TEST_NOW)

    # Data should not have changed
    builder_state_data = memcache.get(builderstate.MEMCACHE_KEY)
    self.assertEquals(TEST_BUILDER_STATE_DATA, builder_state_data)

  def test_refresh_all_data_no_builder_data(self):
    result = builderstate.BuilderState.refresh_all_data()
    self.assertIsNone(result)
    self.assertIsNone(memcache.get(builderstate.MEMCACHE_KEY))

  def test_refresh_all_data_no_files(self):
    memcache.set('buildbot_data', TEST_BUILDERS_DATA)
    result = builderstate.BuilderState.refresh_all_data()
    self.assertIsNotNone(result)
    builder_state = json.loads(result)

    self.assertEqual(TEST_BUILDER_STATE, builder_state)

  def test_refresh_all_data_with_files(self):
    memcache.set('buildbot_data', TEST_BUILDERS_DATA)

    @staticmethod
    def mocked_last_upload_date(master_name, builder, test_type):
      if master_name == TEST_MASTER and builder == TEST_BUILDER and test_type == TEST_TEST_TYPE:
        return TEST_NOW
      return None
    self.mock(
        builderstate.BuilderState, '_get_last_upload_date',
        mocked_last_upload_date)

    result = builderstate.BuilderState.refresh_all_data()
    self.assertIsNotNone(result)
    builder_state = json.loads(result)

    self._validate_builder_state(builder_state)

  def test_get_last_upload_date_unknown_file(self):
    self.assertIsNone(
        builderstate.BuilderState._get_last_upload_date(
            TEST_MASTER,
            TEST_BUILDER,
            TEST_TEST_TYPE))

  def _addFileAndAssert(self, file_data):
    _, code = testfile.TestFile.add_file(*file_data)
    self.assertEqual(
        200, code, 'Unable to create file with data: %s' % file_data)

  def test_get_last_upload_date_with_file(self):
    before_time = datetime.now()
    self._addFileAndAssert(TEST_FILE)
    result = builderstate.BuilderState._get_last_upload_date(
        TEST_MASTER, TEST_BUILDER, TEST_TEST_TYPE)
    after_time = datetime.now()
    self.assertIsNotNone(result)
    self.assertTrue(result >= before_time)
    self.assertTrue(result <= after_time)
