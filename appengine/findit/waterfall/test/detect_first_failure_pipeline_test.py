# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.wf_build import WfBuild
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import buildbot
from waterfall import detect_first_failure_pipeline
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall import lock_util


class DetectFirstFailureTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def setUp(self):
    super(DetectFirstFailureTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

    def _WaitUntilDownloadAllowed(*_):
      return True

    self.mock(lock_util, 'WaitUntilDownloadAllowed', _WaitUntilDownloadAllowed)

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def testBuildDataNeedUpdating(self):
    build = WfBuild.Create('m', 'b', 1)
    pipeline = DetectFirstFailurePipeline('m', 'b', 1)

    # Build data is not available.
    self.assertTrue(pipeline._BuildDataNeedUpdating(build))

    # Build was not completed and data is not recent.
    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    self.assertTrue(pipeline._BuildDataNeedUpdating(build))

  def testBuildDataNotNeedUpdating(self):
    build = WfBuild.Create('m', 'b', 1)
    pipeline = DetectFirstFailurePipeline('m', 'b', 1)

    # Build is not completed yet but data is recent.
    build.data = 'dummy'
    build.completed = False
    build.last_crawled_time = self._TimeBeforeNowBySeconds(60)
    self.assertFalse(pipeline._BuildDataNeedUpdating(build))

    # Build was completed and data is final.
    build.data = 'dummy'
    build.completed = True
    build.last_crawled_time = self._TimeBeforeNowBySeconds(360)
    self.assertFalse(pipeline._BuildDataNeedUpdating(build))


  def _CreateAndSaveWfAnanlysis(
      self, master_name, builder_name, build_number, status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def _GetBuildData(self, master_name, builder_name, build_number):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data',
        '%s_%s_%d.json' % (master_name, builder_name, build_number))
    with open(file_name, 'r') as f:
      return f.read()

  def _MockUrlfetchWithBuildData(
      self, master_name, builder_name, build_number, 
      build_data=None, archive=False):
    """If build data is None, use json file in waterfall/test/data."""
    if build_data is None:
      build_data = self._GetBuildData(master_name, builder_name, build_number)

    if archive:
      if build_data == 'Test get build data':
        build_data = build_data + ' from archive'
      archived_build_url = buildbot.CreateArchivedBuildUrl(
          master_name, builder_name, build_number)
      self.mocked_urlfetch.register_handler(archived_build_url, build_data)

    if build_data == 'Test get build data':
      build_data = build_data + ' from build master'
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number, json_api=True)
    self.mocked_urlfetch.register_handler(build_url, build_data)

  def testGetBuildeDataFromArchive(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._MockUrlfetchWithBuildData(master_name, builder_name, 123,
                                    build_data='Test get build data',
                                    archive=True)

    pipeline = DetectFirstFailurePipeline()
    build = pipeline._DownloadBuildData(master_name, builder_name, build_number)

    expected_build_data = 'Test get build data from archive'

    self.assertIsNotNone(build)
    self.assertEqual(expected_build_data, build.data)

  def testGetBuildeDataFromBuildMaster(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._MockUrlfetchWithBuildData(master_name, builder_name, 123,
                                    build_data='Test get build data')

    pipeline = DetectFirstFailurePipeline()
    build = pipeline._DownloadBuildData(master_name, builder_name, build_number)

    expected_build_data = 'Test get build data from build master'

    self.assertIsNotNone(build)
    self.assertEqual(expected_build_data, build.data)

  def testLookBackUntilGreenBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    # 123: mock urlfetch to ensure it is fetched.
    self._MockUrlfetchWithBuildData(master_name, builder_name, 123)
    # 122: mock a build in datastore to ensure it is not fetched again.
    build = WfBuild.Create(master_name, builder_name, 122)
    build.data = self._GetBuildData(master_name, builder_name, 122)
    build.completed = True
    build.put()
    self._MockUrlfetchWithBuildData(
        master_name, builder_name, 122, build_data='Blow up if used!')
    # 121: mock a build in datastore to ensure it is updated.
    build = WfBuild.Create(master_name, builder_name, 121)
    build.data = 'Blow up if used!'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(7200)
    build.completed = False
    build.put()
    self._MockUrlfetchWithBuildData(master_name, builder_name, 121)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'net_unittests': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123
        },
        'unit_tests': {
            'last_pass': 121,
            'current_failure': 123,
            'first_failure': 122
        }
    }

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def testFirstFailureLastPassUpdating(self):
    """last pass always should just be updated once."""
    master_name = 'm'
    builder_name = 'b'
    build_number = 100

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)
    # Setup build data for builds:
    # 100: net_unitests failed, unit_tests failed.
    # 99: net_unitests passed, unit_tests failed.
    # 98: net_unitests passed, unit_tests failed.
    # 97: net_unitests failed, unit_tests failed.
    # 96: net_unitests passed, unit_tests passed.
    for i in range(5):
         self._MockUrlfetchWithBuildData(master_name, builder_name, 100 - i)
  
    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'net_unittests': {
            'last_pass': 99,
            'current_failure': 100,
            'first_failure': 100
        },
        'unit_tests': {
            'last_pass': 96,
            'current_failure': 100,
            'first_failure': 97
        }
    }

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    self._MockUrlfetchWithBuildData(master_name, builder_name, 124)
    self._MockUrlfetchWithBuildData(master_name, builder_name, 123,
                                    build_data=None, archive=True)
    self._MockUrlfetchWithBuildData(
        master_name, builder_name, 122, build_data='Blow up if used!')

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'a': {
            'last_pass': 123,
            'current_failure': 124,
            'first_failure': 124
        }
    }

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])

  def testAnalyzeSuccessfulBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    self._MockUrlfetchWithBuildData(master_name, builder_name, 121)
    self._MockUrlfetchWithBuildData(
        master_name, builder_name, 120, build_data='Blow up if used!')

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    self.assertFalse(failure_info['failed'])

  def testStopLookingBackIfFindTheFirstBuild(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2

    self._CreateAndSaveWfAnanlysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    # Setup build data for builds:
    self._MockUrlfetchWithBuildData(master_name, builder_name, 2)
    self._MockUrlfetchWithBuildData(master_name, builder_name, 1)
    self._MockUrlfetchWithBuildData(master_name, builder_name, 0)

    pipeline = DetectFirstFailurePipeline()
    failure_info = pipeline.run(master_name, builder_name, build_number)

    expected_failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 0
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 0
        }
    }

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])
