# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import webapp2

from testing_utils import testing

from common.git_repository import GitRepository
from handlers import help_triage
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from waterfall import buildbot
from waterfall.build_info import BuildInfo
from waterfall import build_util


EXPECTED_RESULTS_120 = {
    '598ed4fa15e6a1d0d92b2b7df04fc31ab5d6e829': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/12578123',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/121'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/120'),
        'fixed_build_number': 120,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1280463001',
        'fixing_cl_commit_position': 342013,
        'fixed_cl_commit_position': 341971,
        'fixed_revision': '598ed4fa15e6a1d0d92b2b7df04fc31ab5d6e829',
        'fixing_build_number': 121,
        'action': 'Reverted',
        'fixing_revision': '598sd489df74g125svf35s04fc3'
    },
    '062a6f974d7c08d27902060c241149ce193e4dd5': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/1268183002',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/121'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/120'),
        'fixed_build_number': 120,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1280463006',
        'fixing_cl_commit_position': 342015,
        'fixed_cl_commit_position': 341977,
        'fixed_revision': '062a6f974d7c08d27902060c241149ce193e4dd5',
        'fixing_build_number': 121,
        'action': 'Reverted',
        'fixing_revision': '123456789c08d27902060c241149ce193e4dd5dd'
    },
    '584de1b73f811bcdb98eae1fb0d92b2b7df04fc3': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/1263223005',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/122'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/120'),
        'fixed_build_number': 120,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1280463003',
        'fixing_cl_commit_position': 342014,
        'fixed_cl_commit_position': 341976,
        'fixed_revision': '584de1b73f811bcdb98eae1fb0d92b2b7df04fc3',
        'fixing_build_number': 122,
        'action': 'Reverted',
        'fixing_revision': '123456671bcdb98eae1fb0d92b2b7df04fc3'
    },
    '3e4aaaa45c528d4ab0670331a6c0ebfc4f3ab8e6': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/1260813007',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/123'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/120'),
        'fixed_build_number': 120,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1280463100',
        'fixing_cl_commit_position': 332070,
        'fixed_cl_commit_position': 341978,
        'fixed_revision': '3e4aaaa45c528d4ab0670331a6c0ebfc4f3ab8e6',
        'fixing_build_number': 123,
        'action': 'Reverted',
        'fixing_revision': '123455668d4ab0670331a6c0ebfc4f3ab8e6'
    }
}

EXPECTED_RESULTS_121 = {
    '3e4aaaa45c528d4ab0670331a6c0ebfc4f3ab8e6': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/1260813007',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/123'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/120'),
        'fixed_build_number': 120,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1280463100',
        'action': 'Reverted',
        'fixed_cl_commit_position': 341978,
        'fixed_revision': '3e4aaaa45c528d4ab0670331a6c0ebfc4f3ab8e6',
        'fixing_build_number': 123,
        'fixing_cl_commit_position': 332070,
        'fixing_revision': '123455668d4ab0670331a6c0ebfc4f3ab8e6'
    },
    '584de1b73f811bcdb98eae1fb0d92b2b7df04fc3': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/1263223005',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/122'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/120'),
        'fixed_build_number': 120,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1280463003',
        'action': 'Reverted',
        'fixed_cl_commit_position': 341976,
        'fixed_revision': '584de1b73f811bcdb98eae1fb0d92b2b7df04fc3',
        'fixing_build_number': 122,
        'fixing_cl_commit_position': 342014,
        'fixing_revision': '123456671bcdb98eae1fb0d92b2b7df04fc3'
    },
    '123456789c08d27902060c241149ce193e4dd5dd': {
        'fixed_cl_review_url': 'https://codereview.chromium.org/1280463006',
        'fixing_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/122'),
        'fixed_build_url': (
            'https://build.chromium.org/p/m/builders/b/builds/121'),
        'fixed_build_number': 121,
        'fixing_cl_review_url': 'https://codereview.chromium.org/1161773008',
        'action': 'Reverted',
        'fixed_cl_commit_position': 342015,
        'fixed_revision': '123456789c08d27902060c241149ce193e4dd5dd',
        'fixing_build_number': 122,
        'fixing_cl_commit_position': 332062,
        'fixing_revision': '062a6f974d7c01234569ce193e4dd5'
    }
}



class HelpTriageTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/help-triage', help_triage.HelpTriage),
  ], debug=True)

  def _GetBuildInfo(self, master_name, builder_name, build_number):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data', 'help_triage_test_data',
        'build_data_%s_%s_%s.json' % (
            master_name, builder_name, build_number))
    if not os.path.isfile(file_name):
      return None
    with open(file_name, 'r') as f:
      return f.read()

  def _MockDownloadBuildData(
      self, master_name, builder_name, build_number):
    build = WfBuild.Get(master_name, builder_name, build_number)
    if not build:  # pragma: no cover
      build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = self._GetBuildInfo(master_name, builder_name, build_number)
    build.put()
    return build

  def _MockDownloadChangeLogData(self, revision):
    file_name = os.path.join(
        os.path.dirname(__file__), 'data', 'help_triage_test_data',
        'change_log_' + revision)
    with open(file_name) as f:
      commit_log = f.read()
    return revision, json.loads(commit_log[len(')]}\'\n'):])

  def setUp(self):
    super(HelpTriageTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    self.mock(build_util, 'DownloadBuildData',
              self._MockDownloadBuildData)
    self.mock(GitRepository, '_DownloadChangeLogData',
              self._MockDownloadChangeLogData)

  def _CreateAnalysis(self, build_number, first_failure, last_pass=None):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, build_number)
    analysis.result = {
      'failures': [
        {
          'last_pass': last_pass,
          'first_failure': first_failure,
          'suspected_cls': [],
          'step_name': 'gn_check'
        }
      ]
    }
    analysis.put()

  def testGetFirstFailedBuild(self):
    self._CreateAnalysis(120, 118, 117)
    first_build, failed_steps = help_triage._GetFirstFailedBuild(
        self.master_name, self.builder_name, 120)
    self.assertEqual(118, first_build)
    self.assertEqual(['gn_check'], failed_steps)

  def testGetFirstFailedBuildNoLastPass(self):
    self._CreateAnalysis(120, 118)
    first_build, failed_steps = help_triage._GetFirstFailedBuild(
        self.master_name, self.builder_name, 120)
    self.assertEqual(118, first_build)
    self.assertEqual(['gn_check'], failed_steps)

  def testGetFirstFailedBuildNoAnalysis(self):
    first_build, failed_steps = help_triage._GetFirstFailedBuild(
        self.master_name, self.builder_name, 120)
    self.assertIsNone(first_build)
    self.assertIsNone(failed_steps)

  def testCheckReverts(self):
    self._CreateAnalysis(120, 120)

    results = help_triage._CheckReverts(
        self.master_name, self.builder_name, 120)

    self.assertEqual(EXPECTED_RESULTS_120, results)

  def testCheckRevertsReturnNoneWhenNoGreenBuild(self):
    self._CreateAnalysis(124, 124)

    expected_results = {}
    results = help_triage._CheckReverts(
        self.master_name, self.builder_name, 124)
    self.assertEqual(expected_results, results)

  def testCheckRevertsReturnNoneWhenNoReverts(self):
    self._CreateAnalysis(118, 118)

    expected_results = {}
    results = help_triage._CheckReverts(
        self.master_name, self.builder_name, 118)
    self.assertEqual(expected_results, results)

  def testHelpTriageHandler(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, 121)
    analysis = WfAnalysis.Create(self.master_name, self.builder_name, 121)
    analysis.result = {
      'failures': [
        {
          'last_pass': None,
          'first_failure': 120,
          'suspected_cls': [],
          'step_name': 'gn_check'
        }
      ]
    }
    analysis.put()

    response = self.test_app.get('/help-triage', params={'url': build_url})

    self.assertEqual(200, response.status_int)
    self.assertEqual(EXPECTED_RESULTS_121, response.json_body)

  def testHelpTriageHandlerReturnNoneForGreenBuild(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, 123)
    build = WfBuild.Create(self.master_name, self.builder_name, 123)
    build.data = self._GetBuildInfo(self.master_name, self.builder_name, 123)
    build.put()

    response = self.test_app.get('/help-triage', params={'url': build_url})
    expected_results = {}

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body)
