# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from model.wf_build import WfBuild
from waterfall import build_util
from waterfall import buildbot
from waterfall.test import wf_testcase


class BuildUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(BuildUtilTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def testBuildDataNeedUpdating(self):
    build = WfBuild.Create('m', 'b', 1)

    # Build data is not available.
    self.assertTrue(build_util._BuildDataNeedUpdating(build))

    # Build was not completed and data is not recent.
    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    self.assertTrue(build_util._BuildDataNeedUpdating(build))

  def testBuildDataNotNeedUpdating(self):
    build = WfBuild.Create('m', 'b', 1)

    # Build is not completed yet but data is recent.
    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(60)
    self.assertFalse(build_util._BuildDataNeedUpdating(build))

    # Build was completed and data is final.
    build.data = 'dummy'
    build.completed = True
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    self.assertFalse(build_util._BuildDataNeedUpdating(build))

  def testGetBuildDataNotDownloadAgain(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)

    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(60)
    build.put()

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    expected_build_data = 'dummy'

    self.assertEqual(expected_build_data, build.data)

  @mock.patch.object(
      buildbot,
      'GetBuildDataFromMilo',
      return_value='Test get build data from build master')
  def testGetBuildDataFromMilo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    build = build_util.DownloadBuildData(master_name, builder_name,
                                         build_number)

    expected_build_data = 'Test get build data from build master'

    self.assertEqual(expected_build_data, build.data)

  @mock.patch.object(
      buildbot,
      'GetBuildDataFromMilo',
      return_value='Test get build data from milo')
  def testDownloadBuildDataSourceFromBM(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.put()

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data, 'Test get build data from milo')

  @mock.patch.object(
      buildbot,
      'GetBuildDataFromMilo',
      return_value='Test get build data from milo updated')
  def testDownloadBuildDataSourceFromBMUpateBuildData(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = 'Original build data'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    build.put()

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data, 'Test get build data from milo updated')

  def testGetBuildEndTime(self):
    cases = {
        'null': None,
        '1467740016': datetime.datetime(2016, 7, 5, 17, 33, 36),
    }
    for end_time, expected_time in cases.iteritems():
      master_name = 'm'
      builder_name = 'b'
      build_number = 123
      build = WfBuild.Create(master_name, builder_name, build_number)
      build.data = '{"times": [1467738821, %s]}' % end_time
      build.completed = True
      build.last_crawled_time = self._TimeBeforeNowBySeconds(10)
      build.put()

      self.assertEqual(expected_time,
                       build_util.GetBuildEndTime(master_name, builder_name,
                                                  build_number))

  def testCreateBuildId(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    self.assertEqual(
        build_util.CreateBuildId(master_name, builder_name, build_number),
        'm/b/1')

  def testGetBuildInfoFromId(self):
    build_id = 'm/b/1'
    self.assertEqual(build_util.GetBuildInfoFromId(build_id), ['m', 'b', '1'])

  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfo(self, mocked_fn):
    build = WfBuild.Create('m', 'b', 123)
    build.data = json.dumps({
        'properties': [['got_revision', 'a_git_hash'],
                       ['got_revision_cp', 'refs/heads/master@{#12345}']],
    })
    mocked_fn.return_value = build

    build_info = build_util.GetBuildInfo('m', 'b', 123)
    self.assertEqual(build_info.chromium_revision, 'a_git_hash')

  @mock.patch.object(build_util, 'DownloadBuildData')
  def testGetBuildInfoBuildNotAvailable(self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {}
    mocked_fn.return_value = build

    self.assertIsNone(
        build_util.GetBuildInfo(master_name, builder_name, build_number))
