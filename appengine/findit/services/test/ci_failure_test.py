# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import os

from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from services import ci_failure
from waterfall import buildbot
from waterfall import build_util
from waterfall.test import wf_testcase


class CIFailureServicesTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CIFailureServicesTest, self).setUp()

    with self.mock_urlfetch() as urlfetch:
      self.mocked_urlfetch = urlfetch

  def _TimeBeforeNowBySeconds(self, seconds):
    return datetime.datetime.utcnow() - datetime.timedelta(0, seconds, 0)

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number,
                                status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def _GetBuildData(self, master_name, builder_name, build_number):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data',
        '%s_%s_%d.json' % (master_name, builder_name, build_number))
    with open(file_name, 'r') as f:
      return f.read()

  @mock.patch.object(ci_failure, '_ExtractBuildInfo', return_value=None)
  def testFailedToExtractBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failed_steps = {'a': {'current_failure': 124, 'first_failure': 124}}
    builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    failure_info = {'failed_steps': failed_steps, 'builds': builds}
    failure_info = ci_failure.CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(failed_steps, failure_info['failed_steps'])

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testStopLookingBackIfAllFailedStepsPassedInLastBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    failed_steps = {'a': {'current_failure': 124, 'first_failure': 124}}
    builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [self._GetBuildData(master_name, builder_name, 123)]

    expected_failed_steps = {
        'a': {
            'last_pass': 123,
            'current_failure': 124,
            'first_failure': 124
        }
    }

    expected_builds = {
        124: {
            'chromium_revision': 'some_git_hash',
            'blame_list': ['some_git_hash']
        },
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }

    failure_info = {'failed_steps': failed_steps, 'builds': builds}
    failure_info = ci_failure.CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failure_info)

    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])
    self.assertEqual(expected_builds, failure_info['builds'])

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testStopLookingBackIfFindTheFirstBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    failed_steps = {
        'a_tests': {
            'current_failure': 2,
            'first_failure': 2
        },
        'unit_tests': {
            'current_failure': 2,
            'first_failure': 2
        }
    }
    builds = {
        '2': {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    mock_fn.side_effect = [
        self._GetBuildData(master_name, builder_name, 1),
        self._GetBuildData(master_name, builder_name, 0)
    ]

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

    expected_builds = {
        2: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        1: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        0: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
    }

    failure_info = {'failed_steps': failed_steps, 'builds': builds}

    failure_info = ci_failure.CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failure_info)
    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])
    self.assertEqual(expected_builds, failure_info['builds'])

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testLookBackUntilGreenBuild(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    failed_steps = {
        'net_unittests': {
            'current_failure': 123,
            'first_failure': 123
        },
        'unit_tests': {
            'current_failure': 123,
            'first_failure': 123
        }
    }
    builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.RUNNING)

    # Setup build data for builds:
    # 122: mock a build in datastore to ensure it is not fetched again.
    build = WfBuild.Create(master_name, builder_name, 122)
    build.data = self._GetBuildData(master_name, builder_name, 122)
    build.completed = True
    build.put()
    # 121: mock a build in datastore to ensure it is updated.
    build = WfBuild.Create(master_name, builder_name, 121)
    build.data = 'Blow up if used!'
    build.last_crawled_time = self._TimeBeforeNowBySeconds(7200)
    build.completed = False
    build.put()

    mock_fn.side_effect = [self._GetBuildData(master_name, builder_name, 121)]

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

    expected_builds = {
        123: {
            'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
            'blame_list': ['64c72819e898e952103b63eabc12772f9640af07']
        },
        122: {
            'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': ['5934404dc5392ab3ae2c82b52b366889fb858d91']
        },
        121: {
            'chromium_revision':
                '5934404dc5392ab3ae2c82b52b366889fb858d91',
            'blame_list': [
                '2fe8767f011a20ed8079d3aba7008acd95842f79',
                'c0ed134137c98c2935bf32e85f74d4e94c2b980d',
                '63820a74b4b5a3e6707ab89f92343e7fae7104f0'
            ]
        }
    }

    failure_info = {'failed_steps': failed_steps, 'builds': builds}

    failure_info = ci_failure.CheckForFirstKnownFailure(
        master_name, builder_name, build_number, failure_info)
    self.assertEqual(expected_failed_steps, failure_info['failed_steps'])
    self.assertEqual(expected_builds, failure_info['builds'])

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testGetBuildFailureInfo(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    mock_fn.return_value = self._GetBuildData(master_name, builder_name,
                                              build_number)

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    expected_failure_info = {
        'failed': True,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07',
        'builds': {
            build_number: {
                'blame_list': ['64c72819e898e952103b63eabc12772f9640af07'],
                'chromium_revision': '64c72819e898e952103b63eabc12772f9640af07'
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': build_number,
                'first_failure': build_number
            }
        },
        'failure_type': failure_type.TEST,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    self.assertEqual(expected_failure_info, failure_info)
    self.assertTrue(should_proceed)

  @mock.patch.object(ci_failure, '_ExtractBuildInfo', return_value=None)
  def testGetBuildFailureInfoFailedGetBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    self.assertEqual({}, failure_info)
    self.assertFalse(should_proceed)

  @mock.patch.object(buildbot, 'GetBuildDataFromMilo')
  def testGetBuildFailureInfoBuildSuccess(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number,
                                   analysis_status.PENDING)

    mock_fn.return_value = self._GetBuildData(master_name, builder_name,
                                              build_number)

    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)

    expected_failure_info = {
        'failed': False,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'chromium_revision': '5934404dc5392ab3ae2c82b52b366889fb858d91',
        'builds': {},
        'failed_steps': {},
        'failure_type': failure_type.UNKNOWN,
        'parent_mastername': None,
        'parent_buildername': None,
    }

    self.assertEqual(expected_failure_info, failure_info)
    self.assertFalse(should_proceed)

  @mock.patch.object(build_util, 'DownloadBuildData', return_value=None)
  def testExtractBuildInfo(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 121

    with self.assertRaises(Exception):
      ci_failure._ExtractBuildInfo(master_name, builder_name, build_number)

  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(buildbot, 'GetBuildResult')
  def testAnyNewBuildSucceededPassedThenFailed(self, mock_fn, *_):
    mock_fn.side_effect = [buildbot.SUCCESS, buildbot.FAILURE]
    self.assertTrue(ci_failure.AnyNewBuildSucceeded('m', 'b', 123))

  @mock.patch.object(
      buildbot, 'GetBuildDataFromMilo', return_value='{"data": "data"}')
  @mock.patch.object(
      buildbot, 'GetRecentCompletedBuilds', return_value=[125, 124])
  @mock.patch.object(buildbot, 'GetBuildResult')
  def testAnyNewBuildSucceeded(self, mock_fn, *_):
    mock_fn.side_effect = [buildbot.FAILURE, buildbot.FAILURE]
    self.assertFalse(ci_failure.AnyNewBuildSucceeded('m', 'b', 123))
