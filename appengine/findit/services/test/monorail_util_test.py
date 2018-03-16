# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest
import urllib

from dto.test_location import TestLocation
from services import monorail_util
from services import swarmed_test_util
from services import swarming
from services import test_results

class MonorailHelperTest(unittest.TestCase):
  @mock.patch.object(
      monorail_util, 'GetGTestComponent', return_value='component')
  @mock.patch.object(swarming, 'GetIsolatedDataForStep')
  @mock.patch.object(swarmed_test_util,
                     'RetrieveShardedTestResultsFromIsolatedServer')
  def testGetComponentGTest(self, results_fn, isolate_fn, get_component_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'

    self.assertEqual('component',
                     monorail_util.GetComponent(
                         None, master_name, builder_name, build_number,
                         step_name, test_name))
    isolate_fn.assert_called_with(master_name, builder_name, build_number,
                                  step_name, None)
    results_fn.assert_called()
    get_component_fn.assert_called()

  @mock.patch.object(
      monorail_util, 'GetGTestComponent', return_value='component')
  @mock.patch.object(swarming, 'GetIsolatedDataForStep', return_value=None)
  @mock.patch.object(swarmed_test_util,
                     'RetrieveShardedTestResultsFromIsolatedServer')
  def testGetComponentGTestNoIsolateData(self, results_fn, isolate_fn,
                                         get_component_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'

    self.assertEqual(None,
                     monorail_util.GetComponent(
                         None, master_name, builder_name, build_number,
                         step_name, test_name))
    isolate_fn.assert_called_with(master_name, builder_name, build_number,
                                  step_name, None)
    results_fn.assert_not_called()
    get_component_fn.assert_not_called()

  @mock.patch.object(
      monorail_util, 'GetGTestComponent', return_value='component')
  @mock.patch.object(swarming, 'GetIsolatedDataForStep')
  @mock.patch.object(
      swarmed_test_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value=None)
  def testGetComponentGTestNoResults(self, results_fn, isolate_fn,
                                         get_component_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'

    self.assertEqual(None,
                     monorail_util.GetComponent(
                         None, master_name, builder_name, build_number,
                         step_name, test_name))
    isolate_fn.assert_called_with(master_name, builder_name, build_number,
                                  step_name, None)
    results_fn.assert_called()
    get_component_fn.assert_not_called()

  @mock.patch.object(
      monorail_util,
      'GetNearestComponentForPath',
      return_value='component')
  def testGetComponentLayoutTest(self, get_component_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = '__layout__test'
    test_name = 't'

    self.assertEqual('component',
                     monorail_util.GetComponent(
                         None, master_name, builder_name, build_number,
                         step_name, test_name))
    get_component_fn.assert_called_with(
        'third_party/WebKit/LayoutTests/' + test_name)

  @mock.patch.object(test_results, 'GetTestLocation')
  @mock.patch.object(
      monorail_util,
      'GetNearestComponentForPath',
      return_value='chromium>foo')
  def testGetGTestComponent(self, get_component_fn, get_location_fn):
    test_name = 'test'
    results = {'foo': 'bar'}

    get_location_fn.return_value = TestLocation(file='foo/bar.cc', line=1), None
    self.assertEqual('chromium>foo',
                     monorail_util.GetGTestComponent(
                         test_name, results))
    get_location_fn.assert_called_with(results, test_name)
    get_component_fn.assert_called_with('foo/bar.cc')

  @mock.patch.object(test_results, 'GetTestLocation')
  @mock.patch.object(
      monorail_util,
      'GetNearestComponentForPath',
      return_value='chromium>foo')
  def testGetGTestComponentNoLocation(self, get_component_fn, get_location_fn):
    test_name = 'test'
    results = {'foo': 'bar'}

    get_location_fn.return_value = None, None
    self.assertEqual(None,
                     monorail_util.GetGTestComponent(
                         test_name, results))
    get_location_fn.assert_called_with(results, test_name)
    get_component_fn.assert_not_called()

  @mock.patch.object(urllib, 'urlopen')
  def testGetNearestComponentForPath(self, url_fn):
    path = 'foo/bar/baz'
    read_fn = mock.Mock()
    read_fn.read.return_value = ('{'
                                 '"dir-to-component": {'
                                 '"foo/bar": "chromium>foo"'
                                 '}'
                                 '}')
    url_fn.return_value = read_fn
    self.assertEqual('chromium>foo',
                     monorail_util.GetNearestComponentForPath(path))

  @mock.patch.object(urllib, 'urlopen')
  def testGetNearestComponentForPathNoMatch(self, url_fn):
    path = 'b/a/baz'
    read_fn = mock.Mock()
    read_fn.read.return_value = ('{'
                                 '"dir-to-component": {'
                                 '"foo/bar": "chromium>foo"'
                                 '}'
                                 '}')
    url_fn.return_value = read_fn
    self.assertEqual(None,
                     monorail_util.GetNearestComponentForPath(path))