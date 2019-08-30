# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.step_pb2 import Step

from findit_v2.services import build_util
from findit_v2.services.context import Context
from findit_v2.services.failure_type import StepTypeEnum


class BuildUtilTest(unittest.TestCase):

  def testGetFailedStepsInBuild(self):
    build_id = 8000000000123
    build_number = 123
    builder = BuilderID(project='chromium', bucket='try', builder='linux-rel')
    build = Build(
        id=build_id,
        builder=builder,
        number=build_number,
        status=common_pb2.FAILURE)
    step1 = Step(name='s1', status=common_pb2.SUCCESS)
    step2 = Step(name='compile', status=common_pb2.FAILURE)
    build.steps.extend([step1, step2])

    context = Context(
        luci_project_name='chromium',
        gitiles_host='gitiles.host.com',
        gitiles_project='project/name',
        gitiles_ref='ref/heads/master',
        gitiles_id='git_sha')

    failed_steps = build_util.GetFailedStepsInBuild(context, build)
    self.assertEqual(1, len(failed_steps))
    self.assertEqual('compile', failed_steps[0][0].name)
    self.assertEqual(StepTypeEnum.COMPILE, failed_steps[0][1])

  def testGetAnalyzedBuildIdFromRerunBuild(self):
    analyzed_build_id = 8000000000123
    build = Build(tags=[{
        'key': 'analyzed_build_id',
        'value': str(analyzed_build_id)
    }])
    self.assertEqual(analyzed_build_id,
                     build_util.GetAnalyzedBuildIdFromRerunBuild(build))

  def testGetAnalyzedBuildIdFromRerunBuildNoAnalyzedBuildId(self):
    self.assertIsNone(build_util.GetAnalyzedBuildIdFromRerunBuild(Build()))

  @mock.patch(
      'common.waterfall.buildbucket_client.GetV2Build', return_value=None)
  def testGetBuildAndContextForAnalysisNoBuild(self, _):
    self.assertEqual((None, None),
                     build_util.GetBuildAndContextForAnalysis('chromium', 123))
