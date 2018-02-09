# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.test_location import TestLocation
from services import swarmed_test_util
from waterfall import swarming_util
from waterfall.test import wf_testcase


class SwarmedTestUtilTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask', return_value={})
  def testGetTestLocationNoTestLocations(self, _):
    self.assertIsNone(swarmed_test_util.GetTestLocation('task', 'test'))

  @mock.patch.object(
      swarming_util,
      'GetIsolatedOutputForTask',
      return_value={
          'test_locations': {}
      })
  def testGetTestLocationNoTestLocation(self, _):
    self.assertIsNone(swarmed_test_util.GetTestLocation('task', 'test'))

  @mock.patch.object(
      swarming_util,
      'GetIsolatedOutputForTask',
      return_value={
          'test_locations': {
              'test': {}
          }
      })
  def testGetTestLocationTestLocationIncomplete(self, _):
    self.assertIsNone(swarmed_test_util.GetTestLocation('task', 'test'))

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask')
  def testGetTestLocation(self, mock_get_isolated_output):
    test_name = 'test'
    expected_test_location = {
        'line': 123,
        'file': '/path/to/test_file.cc',
    }
    mock_get_isolated_output.return_value = {
        'test_locations': {
            test_name: expected_test_location,
        }
    }

    self.assertEqual(
        TestLocation.FromSerializable(expected_test_location),
        swarmed_test_util.GetTestLocation('task', test_name))
