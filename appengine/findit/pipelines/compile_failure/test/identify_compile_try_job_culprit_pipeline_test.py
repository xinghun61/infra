# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.dict_of_basestring import DictOfBasestring
from gae_libs.pipelines import pipeline_handlers
from libs.list_of_basestring import ListOfBasestring
from pipelines.compile_failure import (identify_compile_try_job_culprit_pipeline
                                       as culprit_pipeline)
from pipelines.compile_failure import (
    revert_and_notify_compile_culprit_pipeline as revert_pipeline)
from model.wf_suspected_cl import WfSuspectedCL
from services.compile_failure import compile_try_job
from services.parameters import BuildKey
from services.parameters import CompileTryJobResult
from services.parameters import CulpritActionParameters
from services.parameters import IdentifyCompileTryJobCulpritParameters
from waterfall.test import wf_testcase


class IdentifyCompileTryJobCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(
      compile_try_job, 'IdentifyCompileTryJobCulprit', return_value=({}, []))
  @mock.patch.object(revert_pipeline, 'RevertAndNotifyCompileCulpritPipeline')
  def testIdentifyCulpritForCompileTryJobNoCulprit(self, mock_revert_pipeline,
                                                   _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    try_job_result = {'try_job_id': try_job_id, 'url': 'url', 'report': None}
    pipeline_input = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(try_job_result))
    pipeline = culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        pipeline_input)
    pipeline.start()
    self.execute_queued_tasks()
    self.assertFalse(mock_revert_pipeline.called)

  @mock.patch.object(compile_try_job, 'IdentifyCompileTryJobCulprit')
  def testIdentifyCulpritForCompileTryJobSuccess(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'culprit': 'rev2'
        },
        'try_job_id': try_job_id,
    }

    repo_name = 'chromium'
    revision = 'rev2'

    culprit = WfSuspectedCL.Create(repo_name, revision, 100)
    culprit.put()

    culprits_result = {
        'rev2': {
            'revision': revision,
            'commit_position': 2,
            'url': 'url_2',
            'repo_name': repo_name
        }
    }
    mock_fn.return_value = culprits_result, ListOfBasestring()

    culprits = DictOfBasestring()
    culprits['rev2'] = culprit.key.urlsafe()

    self.MockGeneratorPipeline(
        pipeline_class=revert_pipeline.RevertAndNotifyCompileCulpritPipeline,
        expected_input=CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=ListOfBasestring(),
            failure_to_culprit_map=None),
        mocked_output=False)

    pipeline_input = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(compile_result))
    pipeline = culprit_pipeline.IdentifyCompileTryJobCulpritPipeline(
        pipeline_input)
    pipeline.start()
    self.execute_queued_tasks()
