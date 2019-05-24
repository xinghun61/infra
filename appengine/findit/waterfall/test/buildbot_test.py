# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import json
import mock
import unittest

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.rpc_pb2 import SearchBuildsResponse
from buildbucket_proto.step_pb2 import Step

from common import rpc_util
from common.waterfall import buildbucket_client
from libs.http.retry_http_client import RetryHttpClient
from services import git
from waterfall import buildbot


class BuildBotTest(unittest.TestCase):

  def setUp(self):
    super(BuildBotTest, self).setUp()
    self.http_client = RetryHttpClient()
    self.master_name = 'tryserver.m'
    self.wf_master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 123
    self.step_name = 'browser_tests on platform'

    self.stdout_stream = 'stdout_stream'
    self.step_metadata_stream = 'step_metadata_stream'

  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testGetRecentCompletedBuilds(self, mock_fn):
    mock_fn.return_value = SearchBuildsResponse(
        builds=[Build(
            number=34), Build(number=33),
                Build(number=32)])
    self.assertEqual([34, 33, 32],
                     buildbot.GetRecentCompletedBuilds('m', 'b',
                                                       RetryHttpClient()))

  def testGetMasterNameFromUrl(self):
    cases = {
        None: None,
        '': None,
        'https://unknown.host/p/chromium': None,
        'http://build.chromium.org/p/chromium': 'chromium',
        'http://build.chromium.org/p/chromium/builders/Linux': 'chromium',
        'https://abc.def.google.com/i/m1/builders/Linux': 'm1',
        'https://ci.chromium.org/buildbot/m2/b/123': 'm2',
        'https://luci-milo.appspot.com/buildbot/m2/b/123': 'm2',
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.GetMasterNameFromUrl(url)
      self.assertEqual(expected_result, result)

  def testParseBuildUrl(self):
    cases = {
        None:
            None,
        '':
            None,
        'https://unknown.host/p/chromium/builders/Linux/builds/55833':
            None,
        'http://build.chromium.org/p/chromium/builders/Linux':
            None,
        'http://build.chromium.org/p/chromium/builders/Linux/builds/55833': (
            'chromium', 'Linux', 55833),
        ('http://build.chromium.org/p/chromium.win/builders/'
         'Win7%20Tests%20%281%29/builds/33911'): ('chromium.win',
                                                  'Win7 Tests (1)', 33911),
        'https://abc.def.google.com/i/m1/builders/b1/builds/234': ('m1', 'b1',
                                                                   234),
        'https://luci-milo.appspot.com/buildbot/m2/b2/123': ('m2', 'b2', 123),
        'https://ci.chromium.org/buildbot/m2/b2/123': ('m2', 'b2', 123),
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.ParseBuildUrl(url)
      self.assertEqual(expected_result, result)

  @mock.patch.object(buildbot.buildbucket_client,
                     'GetV2BuildByBuilderAndBuildNumber')
  def testParseBuildLongUrl(self, mock_get_master):

    master_name = 'chromium.sandbox'
    mock_build = Build()
    mock_build.input.properties['mastername'] = master_name
    mock_get_master.return_value = mock_build

    cases = {
        'https://ci.chromium.org/p/chromium/builders/luci.chromium.ci'
        '/Linux%20Tests%20SANDBOX/3932': (master_name, 'Linux Tests SANDBOX',
                                          3932),
        'https://luci-milo.appspot.com/p/chromium/builders'
        '/luci.chromium.ci/b2/111': (master_name, 'b2', 111),
        'https://luci-milo.appspot.com/p/chromium/builders/ci/b2/111': (
            master_name, 'b2', 111),
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.ParseBuildUrl(url)
      self.assertEqual(expected_result, result)

  @mock.patch.object(
      buildbot.buildbucket_client,
      'GetV2BuildByBuilderAndBuildNumber',
      return_value=None)
  def testParseBuildLongUrlNoBuilds(self, _):
    cases = [
        'https://ci.chromium.org/p/chromium/builders/ci'
        '/Linux%20Tests%20SANDBOX/3932',
        'https://luci-milo.appspot.com/p/chromium/builders/ci/b2/111',
    ]

    for url in cases:
      self.assertIsNone(buildbot.ParseBuildUrl(url))

  def testParseStepUrl(self):
    cases = {
        None:
            None,
        '':
            None,
        ('https://unknown_host/p/chromium/builders/Linux/builds/55833/'
         '/steps/compile'):
            None,
        'http://build.chromium.org/p/chromium/builders/Linux':
            None,
        ('http://build.chromium.org/p/chromium/builders/Linux/builds/55833'
         '/steps/compile'): ('chromium', 'Linux', 55833, 'compile'),
        ('http://build.chromium.org/p/chromium.win/builders/Win7%20Tests%20'
         '%281%29/builds/33911/steps/interactive_ui'): (
            'chromium.win', 'Win7 Tests (1)', 33911, 'interactive_ui'),
    }

    for url, expected_result in cases.iteritems():
      result = buildbot.ParseStepUrl(url)
      self.assertEqual(expected_result, result)

  def testCreateBuildUrl(self):
    master_name = 'a'
    builder_name = 'Win7 Tests (1)'
    build_number = 123
    expected_url = ('https://ci.chromium.org/buildbot/a/'
                    'Win7%20Tests%20%281%29/123')
    self.assertEqual(
        expected_url,
        buildbot.CreateBuildUrl(master_name, builder_name, build_number))

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetBuildDataFromMiloSuccess(self, mock_fn):
    master_name = 'a'
    builder_name = 'b c'
    build_number = 1

    response = {'data': base64.b64encode('response')}
    mock_fn.return_value = (200, json.dumps(response))

    self.assertEqual(
        (200, 'response'),
        buildbot.GetBuildDataFromMilo(master_name, builder_name, build_number,
                                      self.http_client))

  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', return_value=['rev2', 'rev3'])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  def testExtractBuildInfoFromV2BuildComplete(self, *_):
    master_name = 'chromium.linux'
    builder_name = 'Linux Tests'
    bucket = 'ci'
    build_id = 8765000000056123
    build_number = 56123
    build_start_time = datetime(2019, 5, 21)
    build_end_time = datetime(2019, 5, 21, 1)
    gitiles_id = 'rev4'

    build = Build(
        id=build_id,
        number=build_number,
        builder=BuilderID(
            project='chromium', bucket=bucket, builder=builder_name))
    build.input.gitiles_commit.project = 'chromium/src'
    build.input.gitiles_commit.host = 'chromium.googlesource.com'
    build.input.gitiles_commit.ref = 'refs/heads/master'
    build.input.gitiles_commit.id = gitiles_id
    build.input.properties['$recipe_engine/runtime'] = {'is_luci': True}
    build.input.properties['parent_buildername'] = 'Linux Builder'
    build.input.properties['parent_mastername'] = 'chromium.linux'

    build.create_time.FromDatetime(build_start_time)
    build.end_time.FromDatetime(build_end_time)
    build.status = common_pb2.FAILURE

    step1 = Step(name='s1', status=common_pb2.SUCCESS)
    log = step1.logs.add()
    log.name = 'stdout'
    step2 = Step(name='s2', status=common_pb2.SUCCESS)
    step3 = Step(name='s3', status=common_pb2.FAILURE)
    log = step3.logs.add()
    log.name = 'stdout'
    step4 = Step(name='s4', status=common_pb2.FAILURE)
    step_fr = Step(name='Failure reason', status=common_pb2.FAILURE)
    build.steps.extend([step1, step2, step3, step4, step_fr])

    build_info = buildbot.ExtractBuildInfoFromV2Build(master_name, builder_name,
                                                      build_number, build)

    self.assertEqual(master_name, build_info.master_name)
    self.assertEqual(builder_name, build_info.builder_name)
    self.assertEqual(build_number, build_info.build_number)
    self.assertEqual(build_start_time, build_info.build_start_time)
    self.assertEqual(build_end_time, build_info.build_end_time)
    self.assertEqual(gitiles_id, build_info.chromium_revision)
    self.assertEqual(654332, build_info.commit_position)
    self.assertTrue(build_info.completed)
    self.assertEqual(common_pb2.FAILURE, build_info.result)
    self.assertItemsEqual(['rev2', 'rev3'], build_info.blame_list)
    self.assertItemsEqual(['s3'], build_info.failed_steps)
    self.assertItemsEqual(['s1'], build_info.passed_steps)
    self.assertItemsEqual(['s3', 's4', 'Failure reason'],
                          build_info.not_passed_steps)
    self.assertEqual(bucket, build_info.buildbucket_bucket)
    self.assertEqual(build_id, build_info.buildbucket_id)
    self.assertTrue(build_info.is_luci)

  @mock.patch.object(
      buildbot, 'GetBlameListForV2Build', return_value=['rev2', 'rev3'])
  @mock.patch.object(git, 'GetCommitPositionFromRevision', return_value=654332)
  def testExtractBuildInfoFromV2BuildRunning(self, *_):
    master_name = 'chromium.linux'
    builder_name = 'Linux Tests'
    bucket = 'ci'
    build_id = 8765000000056123
    build_number = 56123
    build_start_time = datetime(2019, 5, 21)
    build_end_time = datetime(2019, 5, 21, 1)
    gitiles_id = 'rev4'

    build = Build(
        id=build_id,
        number=build_number,
        builder=BuilderID(
            project='chromium', bucket=bucket, builder=builder_name))
    build.input.gitiles_commit.project = 'chromium/src'
    build.input.gitiles_commit.host = 'chromium.googlesource.com'
    build.input.gitiles_commit.ref = 'refs/heads/master'
    build.input.gitiles_commit.id = gitiles_id
    build.input.properties['$recipe_engine/runtime'] = {'is_luci': True}
    build.input.properties['parent_buildername'] = 'Linux Builder'
    build.input.properties['parent_mastername'] = 'chromium.linux'

    build.create_time.FromDatetime(build_start_time)
    build.end_time.FromDatetime(build_end_time)
    build.status = common_pb2.STARTED

    step1 = Step(name='s1', status=common_pb2.SUCCESS)
    log = step1.logs.add()
    log.name = 'stdout'
    step2 = Step(name='s2', status=common_pb2.SUCCESS)
    step3 = Step(name='s3', status=common_pb2.FAILURE)
    log = step3.logs.add()
    log.name = 'stdout'
    step4 = Step(name='s4', status=common_pb2.FAILURE)
    step5 = Step(name='s5', status=common_pb2.STARTED)
    build.steps.extend([step1, step2, step3, step4, step5])

    build_info = buildbot.ExtractBuildInfoFromV2Build(master_name, builder_name,
                                                      build_number, build)

    self.assertEqual(master_name, build_info.master_name)
    self.assertEqual(builder_name, build_info.builder_name)
    self.assertEqual(build_number, build_info.build_number)
    self.assertEqual(build_start_time, build_info.build_start_time)
    self.assertEqual(build_end_time, build_info.build_end_time)
    self.assertEqual(gitiles_id, build_info.chromium_revision)
    self.assertEqual(654332, build_info.commit_position)
    self.assertTrue(build_info.completed)
    self.assertEqual(common_pb2.STARTED, build_info.result)
    self.assertItemsEqual(['rev2', 'rev3'], build_info.blame_list)
    self.assertItemsEqual(['s3'], build_info.failed_steps)
    self.assertItemsEqual(['s1'], build_info.passed_steps)
    self.assertItemsEqual(['s3', 's4'], build_info.not_passed_steps)
    self.assertEqual(bucket, build_info.buildbucket_bucket)
    self.assertEqual(build_id, build_info.buildbucket_id)
    self.assertTrue(build_info.is_luci)

  @mock.patch.object(git, 'GetCommitsBetweenRevisionsInOrder')
  @mock.patch.object(buildbucket_client, 'SearchV2BuildsOnBuilder')
  def testGetBlameListForV2Build(self, mock_search_build, mock_revisions):
    gitiles_project = 'chromium/src'
    gitiles_host = 'chromium.googlesource.com'
    gitiles_ref = 'refs/heads/master'

    build = Build()
    build.input.gitiles_commit.project = gitiles_project
    build.input.gitiles_commit.host = gitiles_host
    build.input.gitiles_commit.ref = gitiles_ref
    build.input.gitiles_commit.id = 'rev4'

    previous_build = Build()
    previous_build.input.gitiles_commit.project = gitiles_project
    previous_build.input.gitiles_commit.host = gitiles_host
    previous_build.input.gitiles_commit.ref = gitiles_ref
    previous_build.input.gitiles_commit.id = 'rev1'
    mock_search_build.return_value = SearchBuildsResponse(
        builds=[previous_build])

    expected_blame_list = ['rev4', 'rev3', 'rev2']
    mock_revisions.return_value = expected_blame_list

    self.assertEqual(expected_blame_list,
                     buildbot.GetBlameListForV2Build(build))

    mock_revisions.assert_called_once_with(
        'rev1', 'rev4', 'https://chromium.googlesource.com/chromium/src.git')

  def testGetCommitPosition(self):
    self.assertIsNone(buildbot.GetCommitPosition(None))
    self.assertIsNone(buildbot.GetCommitPosition(''))
    self.assertIsNone(buildbot.GetCommitPosition('not a commit position'))
    self.assertEqual(438538,
                     buildbot.GetCommitPosition('refs/heads/master@{#438538}'))

  def testValidateBuildUrl(self):
    swarm_url = 'https://luci-milo.appspot.com/swarming/task/3595be5002f4bc10'
    non_swarm_url = ('https://luci-milo.appspot.com/buildbot/chromium.linux'
                     '/Linux%20Builder/82087')
    legacy_url = ('http://build.chromium.org/p/chromium/builders/Linux/builds'
                  '/55833')
    bad_url = 'https://badhost.com/bad/build/123'
    self.assertTrue(buildbot.ValidateBuildUrl(swarm_url))
    self.assertTrue(buildbot.ValidateBuildUrl(non_swarm_url))
    self.assertTrue(buildbot.ValidateBuildUrl(legacy_url))
    self.assertFalse(buildbot.ValidateBuildUrl(bad_url))

  def testGetLuciProjectAndBucketForMasterTry(self):
    self.assertEqual(
        ('chromium', 'try'),
        buildbot.GetLuciProjectAndBucketForMaster('tryserver.chromium/linux'))
