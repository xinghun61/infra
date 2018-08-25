# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.dict_of_basestring import DictOfBasestring
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from libs.list_of_basestring import ListOfBasestring
from model.wf_try_job import WfTryJob
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from pipelines.test_failure.identify_test_try_job_culprit_pipeline import (
    IdentifyTestTryJobCulpritPipeline)
from model.wf_suspected_cl import WfSuspectedCL
from services import consistent_failure_culprits
from services.parameters import BuildKey
from services.parameters import CulpritActionParameters
from services.parameters import FailureToCulpritMap
from services.parameters import IdentifyTestTryJobCulpritParameters
from services.parameters import TestTryJobResult
from services.test_failure import test_try_job
from waterfall.test import wf_testcase


class IdentifyTestTryJobCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(consistent_failure_culprits,
                     'GetWfSuspectedClKeysFromCLInfo')
  @mock.patch.object(test_try_job, 'IdentifyTestTryJobCulprits')
  def testIdentifyCulpritForTestTryJobSuccess(self, mock_fn, mock_fn2):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    repo_name = 'chromium'
    revision = 'rev2'

    culprit = WfSuspectedCL.Create(repo_name, revision, 100)
    culprit.put()

    culprits_result = {
        'rev1': {
            'revision': 'rev1',
            'repo_name': 'chromium',
            'commit_position': 1,
            'url': 'url_1'
        },
        'rev2': {
            'revision': revision,
            'commit_position': 2,
            'url': 'url_2',
            'repo_name': repo_name
        }
    }

    culprit_map = {'step': {'test1': 'rev1', 'test2': 'rev2'}}
    mock_fn.return_value = culprits_result, ListOfBasestring.FromSerializable(
        []), FailureToCulpritMap.FromSerializable(culprit_map)

    culprits = DictOfBasestring()
    culprits['rev2'] = culprit.key.urlsafe()
    mock_fn2.return_value = culprits

    self.MockGeneratorPipeline(
        pipeline_class=RevertAndNotifyTestCulpritPipeline,
        expected_input=CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=ListOfBasestring(),
            failure_to_culprit_map=FailureToCulpritMap.FromSerializable(
                culprit_map)),
        mocked_output=False)

    parameters = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=TestTryJobResult.FromSerializable({}))
    pipeline = IdentifyTestTryJobCulpritPipeline(parameters)
    pipeline.start()
    self.execute_queued_tasks()
    mock_fn.assert_called_once_with(parameters)

  def testReturnNoneIfNoTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 8

    WfTryJob.Create(master_name, builder_name, build_number).put()

    self.MockGeneratorPipeline(
        pipeline_class=RevertAndNotifyTestCulpritPipeline,
        expected_input=CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=DictOfBasestring(),
            heuristic_cls=ListOfBasestring(),
            failure_to_culprit_map=None),
        mocked_output=False)
    parameters = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=None)
    pipeline = IdentifyTestTryJobCulpritPipeline(parameters)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job.test_results, [])
    self.assertEqual(try_job.status, analysis_status.COMPLETED)
