# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from testing_utils import testing

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

  def _MockUrlfetchWithBuildData(
      self, master_name, builder_name, build_number,
      build_data=None, archive=False):
    if archive and build_data == 'Test get build data':
      build_data += ' from archive'
      archived_build_url = buildbot.CreateArchivedBuildUrl(
          master_name, builder_name, build_number)
      self.mocked_urlfetch.register_handler(archived_build_url, build_data)

    if build_data == 'Test get build data':
      build_data += ' from build master'
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number, json_api=True)
    self.mocked_urlfetch.register_handler(build_url, build_data)

  def testGetBuildDataNotDownloadAgain(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)

    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(60)
    build.put()

    build_util.DownloadBuildData(
        master_name, builder_name, build_number)

    expected_build_data = 'dummy'

    self.assertEqual(expected_build_data, build.data)

  def testGetBuildDataFromArchive(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    build = WfBuild.Create(master_name, builder_name, build_number)
    build.put()
    self._MockUrlfetchWithBuildData(master_name, builder_name, build_number,
                                    build_data='Test get build data',
                                    archive=True)

    build_util.DownloadBuildData(
        master_name, builder_name, build_number)

    expected_build_data = 'Test get build data from archive'

    self.assertEqual(expected_build_data, build.data)

  def testGetBuildDataFromBuildMaster(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    self._MockUrlfetchWithBuildData(master_name, builder_name, 123,
                                    build_data='Test get build data')

    build = build_util.DownloadBuildData(
        master_name, builder_name, build_number)

    expected_build_data = 'Test get build data from build master'

    self.assertEqual(expected_build_data, build.data)

  def testDownloadBuildDataSourceFromCBE(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.put()

    self.UpdateUnitTestConfigSettings(
        'download_build_data_settings', {'use_chrome_build_extract': True})
    self._MockUrlfetchWithBuildData(master_name, builder_name, build_number,
                                    build_data='Test get build data',
                                    archive=True)

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data_source, build_util.CHROME_BUILD_EXTRACT)

  def testDownloadBuildDataSourceFromBM(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.put()

    self.UpdateUnitTestConfigSettings(
        'download_build_data_settings', {'use_chrome_build_extract': False})
    self._MockUrlfetchWithBuildData(master_name, builder_name, build_number,
                                    build_data='Test get build data')

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data_source, build_util.BUILDBOT_MASTER)

  def testDownloadBuildDataSourceFromBMUpateBuildData(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = 'Original build data'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    build.put()

    self.UpdateUnitTestConfigSettings(
        'download_build_data_settings', {'use_chrome_build_extract': False})
    self._MockUrlfetchWithBuildData(master_name, builder_name, build_number,
                                    build_data='Test get build data')

    build_util.DownloadBuildData(master_name, builder_name, build_number)

    self.assertEqual(build.data_source, build_util.BUILDBOT_MASTER)
    self.assertEqual(build.data, 'Test get build data from build master')
