# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from pipeline_utils.appengine_third_party_pipeline_python_src_pipeline \
    import handlers
from testing_utils import testing

from common import chromium_deps
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import buildbot
from waterfall.analyze_build_failure_pipeline import AnalyzeBuildFailurePipeline
from waterfall import lock_util


class AnalyzeBuildFailurePipelineTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def _MockChangeLog(
      self, urlfetch, user_name, revision, commit_position, file_path):
    url = ('https://chromium.googlesource.com/chromium/src.git/+/%s?format=json'
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

  def _Setup(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.ANALYZING
    analysis.put()

    def MockWaitUntilDownloadAllowed(*_):
      return True
    self.mock(
        lock_util, 'WaitUntilDownloadAllowed', MockWaitUntilDownloadAllowed)

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

    def MockGetChromeDependency(*_):
      return {}
    self.mock(chromium_deps, 'GetChromeDependency', MockGetChromeDependency)

  def testBuildFailurePipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number)
    root_pipeline.start(queue_name='default')
    self.execute_queued_tasks()

    expected_analysis_result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 124,
                'last_pass': 123,
                'suspected_cls': [
                    {
                        'build_number': 124,
                        'repo_name': 'chromium',
                        'revision': 'some_git_hash',
                        'commit_position': 8888,
                        'url': ('https://chromium.googlesource.com/chromium'
                                '/src.git/+/some_git_hash'),
                        'score': 2,
                        'hints': {
                            'modified x.cc (and it was in log)': 2,
                        },
                    }
                ],
            }
        ]
    }

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(wf_analysis_status.ANALYZED, analysis.status)
    self.assertEqual(expected_analysis_result, analysis.result)
    self.assertIsNotNone(analysis.result_status)

  def testBuildFailurePipelineStartWithNoneResultStatus(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number)
    root_pipeline._ResetAnalysis(master_name, builder_name, build_number)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(wf_analysis_status.ANALYZING, analysis.status)
    self.assertIsNone(analysis.result_status)

  def testAnalyzeBuildFailurePipelineAbortedWithAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number)
    root_pipeline._LogUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(wf_analysis_status.ERROR, analysis.status)
    self.assertIsNone(analysis.result_status)

  def testAnalyzeBuildFailurePipelineAbortedWithoutAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number)
    root_pipeline._LogUnexpectedAborting(True)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNone(analysis)

  def testAnalyzeBuildFailurePipelineNotAborted(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    self._Setup(master_name, builder_name, build_number)

    root_pipeline = AnalyzeBuildFailurePipeline(master_name,
                                                builder_name,
                                                build_number)
    root_pipeline._LogUnexpectedAborting(False)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertNotEqual(wf_analysis_status.ERROR, analysis.status)
