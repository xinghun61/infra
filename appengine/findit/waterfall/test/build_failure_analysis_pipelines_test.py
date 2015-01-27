# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.build_analysis import BuildAnalysis
from model.build_analysis_status import BuildAnalysisStatus
from waterfall import build_failure_analysis_pipelines
from waterfall import buildbot
from waterfall import lock_util


class BuildFailureAnalysisPipelinesTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def _CreateAndSaveBuildAnalysis(
      self, master_name, builder_name, build_number, status):
    analysis = BuildAnalysis.CreateBuildAnalysis(
        master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def testAnalysisIsNeededWhenBuildWasNeverAnalyzed(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenNotForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveBuildAnalysis(master_name, builder_name, build_number,
                             BuildAnalysisStatus.ANALYZED)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNeededWhenForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveBuildAnalysis(
        master_name, builder_name, build_number, BuildAnalysisStatus.ANALYZED)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, True)

    self.assertTrue(need_analysis)

  def _MockChangeLog(
      self, urlfetch, user_name, revision, commit_position, file_path):
    url = ('https://chromium.googlesource.com/chromium/src/+/%s?format=json'
           % revision)

    COMMIT_LOG_TEMPLATE = """)]}'
    {
      "commit": "REVISION",
      "tree": "tree_rev",
      "parents": [
        "revX"
      ],
      "author": {
        "name": "USER_NAME@chromium.org",
        "email": "USER_NAME@chromium.org",
        "time": "Wed Jun 11 19:35:32 2014"
      },
      "committer": {
        "name": "USER_NAME@chromium.org",
        "email": "USER_NAME@chromium.org",
        "time": "Wed Jun 11 19:35:32 2014"
      },
      "message":
          "git-svn-id: svn://svn.chromium.org/chromium/src@COMMIT_POSITION bla",
      "tree_diff": [
        {
          "type": "modify",
          "old_id": "idX",
          "old_mode": 33188,
          "old_path": "FILE_PATH",
          "new_id": "idY",
          "new_mode": 33188,
          "new_path": "FILE_PATH"
        }
      ]
    }
    """
    commit_log = COMMIT_LOG_TEMPLATE.replace(
        'REVISION', revision).replace('USER_NAME', user_name).replace(
        'COMMIT_POSITION', str(commit_position)).replace('FILE_PATH', file_path)
    urlfetch.register_handler(url, commit_log)


  def testSuccessfulAnalysisOfBuildFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    def _WaitUntilDownloadAllowed(*_):
      return True

    self.mock(lock_util, 'WaitUntilDownloadAllowed', _WaitUntilDownloadAllowed)

    with self.mock_urlfetch() as urlfetch:
      # Mock build data.
      for i in range(2):
        build_url = buildbot.CreateBuildUrl(
                  master_name, builder_name, build_number - i, json_api=True)
        file_name = os.path.join(os.path.dirname(__file__), 'data',
                                 'm_b_%s.json' % (build_number - i))
        with open(file_name, 'r') as f:
          urlfetch.register_handler(build_url, f.read())

      # Mock step log.
      step_log_url = buildbot.CreateStdioLogUrl(
          master_name, builder_name, build_number, 'a')
      urlfetch.register_handler(
          step_log_url, 'error in file a/b/x.cc:89 ...')

      # Mock change logs.
      self._MockChangeLog(urlfetch, 'user1', 'some_git_hash', 8888, 'a/b/x.cc')
      self._MockChangeLog(
          urlfetch, 'user1', '64c72819e898e952103b63eabc12772f9640af07',
          8887, 'd/e/y.cc')

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, False, 'default')

    self.execute_queued_tasks()

    analysis = BuildAnalysis.GetBuildAnalysis(
        master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(BuildAnalysisStatus.ANALYZED, analysis.status)
