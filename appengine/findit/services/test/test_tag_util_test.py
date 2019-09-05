# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import textwrap

from parameterized import parameterized

from dto.test_location import TestLocation as DTOTestLocation
from libs import test_name_util
from model.flake.flake import TestLocation as NDBTestLocation
from model.flake.flake import TestLocation
from services import step_util
from services import test_tag_util
from waterfall.test.wf_testcase import WaterfallTestCase


class TestTagUtilTest(WaterfallTestCase):

  def testNormalizePath(self):
    self.assertEqual('a/b/c', test_tag_util._NormalizePath('a/b/c'))
    self.assertEqual('a/b/c', test_tag_util._NormalizePath('../../a/b/c'))
    self.assertEqual('a/b/c', test_tag_util._NormalizePath('../../a/b/./c'))
    self.assertEqual('b/c', test_tag_util._NormalizePath('../a/../b/c'))

  @mock.patch.object(
      test_tag_util.FinditHttpClient,
      'Get',
      return_value=(200,
                    json.dumps({
                        'dir-to-component': {
                            'p/dir1': 'a>b',
                            'p/dir2': 'd>e>f',
                        }
                    }), None))
  def testGetChromiumDirectoryToComponentMapping(self, *_):
    self.assertEqual({
        'p/dir1/': 'a>b',
        'p/dir2/': 'd>e>f'
    }, test_tag_util._GetChromiumDirectoryToComponentMapping())

  @mock.patch.object(
      test_tag_util.CachedGitilesRepository,
      'GetSource',
      return_value=textwrap.dedent(r"""
                         {
                           'WATCHLIST_DEFINITIONS': {
                             'watchlist1': {
                               'filepath': 'path/to/source\.cc'
                             },
                             'watchlist2': {
                               'filepath': 'a/to/file1\.cc'\
                                           '|b/to/file2\.cc'
                             }
                           }
                         }"""))
  def testGetChromiumWATCHLISTS(self, *_):
    self.assertEqual({
        'watchlist1': r'path/to/source\.cc',
        'watchlist2': r'a/to/file1\.cc|b/to/file2\.cc',
    }, test_tag_util._GetChromiumWATCHLISTS())

  @mock.patch.object(
      test_tag_util.step_util,
      'GetStepMetadata',
      return_value={'swarm_task_ids': ['t1', 't2']})
  @mock.patch.object(
      test_tag_util.swarmed_test_util,
      'GetTestLocation',
      side_effect=[None, DTOTestLocation(file='../../path/a.cc', line=2)])
  @mock.patch.object(test_name_util, 'GTEST_REGEX')
  def testGetTestLocationGTest(self, mock_regex, *_):
    mock_regex.match.return_value = True
    self.assertEqual(
        'path/a.cc',
        test_tag_util.GetTestLocation(123, 'step_name', 'test_name',
                                      'normalized_test_name').file_path)

  def testGetTestLocationWebkit(self, *_):
    self.assertEqual(
        'third_party/blink/web_tests/normalized_test_name',
        test_tag_util.GetTestLocation(123, 'webkit_layout_tests_step_name',
                                      'test_name',
                                      'normalized_test_name').file_path)

  @mock.patch.object(test_name_util, 'GTEST_REGEX')
  def testGetTestLocationNone(self, mock_regex):
    mock_regex.match.return_value = False
    self.assertIsNone(
        test_tag_util.GetTestLocation(123, 'step_name', 'test_name',
                                      'normalized_test_name'))

  @parameterized.expand([
      ('base/feature/url', 'root>a>b'),
      ('base/not/feature/url', 'root>a'),
      ('not/in/mapping', test_tag_util.DEFAULT_COMPONENT),
  ])
  def testGetTestComponentFromLocation(self, test_location, expected_component,
                                       *_):
    component_mapping = {
        'base/': 'root>a',
        'base/feature/': 'root>a>b',
        'base/feature/url': 'root>a>b>c',
    }
    self.assertEqual(
        expected_component,
        test_tag_util.GetTestComponentFromLocation(
            TestLocation(file_path=test_location), component_mapping))

  @parameterized.expand([
      (
          'step_name',
          'webgl_conformance_vulkan_passthrough_tests',
          ['Blink>WebGL', 'Internals>GPU>Testing'],
      ),
      ('context_lost_tests step_name', None, ['Internals>GPU>Testing']),
      ('step_name_not_in_mapping', None, []),
  ])
  @mock.patch.object(step_util, 'GetCanonicalStepName')
  def testGetTestComponentsForGPUTest(self, step_name, canonical_step_name,
                                      expected_component, mock_get_canonical):
    mock_get_canonical.return_value = canonical_step_name
    self.assertEqual(expected_component,
                     test_tag_util.GetTestComponentsForGPUTest(123, step_name))

  def testGetTagsForGPUTest(self):
    expected_tags = sorted(
        set([
            'gerrit_project::chromium/src',
            'component::Internals>GPU>Testing',
            'component::Blink>WebGL',
        ]))
    actual_tags = test_tag_util.GetTagsForGPUTest(
        {'gerrit_project::chromium/src'},
        ['Internals>GPU>Testing', 'Blink>WebGL'])

    self.assertEqual(expected_tags, actual_tags)

  def testGetTagsFromLocation(self, *_):
    watchlists = {
        'feature': 'base/feature',
        'url': r'base/feature/url_test\.cc',
        'other': 'a/b/c',
    }
    expected_tags = sorted(
        set([
            'gerrit_project::chromium/src',
            'watchlist::feature',
            'watchlist::url',
            'directory::base/feature/',
            'directory::base/',
            'source::base/feature/url_test.cc',
            'component::root>a>b',
            'parent_component::root>a>b',
            'parent_component::root>a',
            'parent_component::root',
        ]))

    actual_tags = test_tag_util.GetTagsFromLocation(
        {'gerrit_project::chromium/src'},
        NDBTestLocation(file_path='base/feature/url_test.cc',), 'root>a>b',
        watchlists)

    self.assertEqual(expected_tags, actual_tags)
