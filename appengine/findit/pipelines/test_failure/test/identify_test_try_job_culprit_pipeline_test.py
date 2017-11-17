# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.wf_try_job import WfTryJob
from pipelines.test_failure.revert_and_notify_test_culprit_pipeline import (
    RevertAndNotifyTestCulpritPipeline)
from pipelines.test_failure.identify_test_try_job_culprit_pipeline import (
    IdentifyTestTryJobCulpritPipeline)
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from services.test_failure import test_try_job
from waterfall.test import wf_testcase


class IdentifyTestTryJobCulpritPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  @mock.patch.object(test_try_job, 'IdentifyTestTryJobCulprits')
  def testIdentifyCulpritForTestTryJobSuccess(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    test_result = {
        'report': {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    }
                }
            },
            'culprits': {
                'a_test': {
                    'a_test1': 'rev1',
                    'a_test2': 'rev2'
                },
            },
            'flakes': {
                'b_test': ['b_test1']
            }
        },
        'url': 'url',
        'try_job_id': try_job_id
    }
    culprits_result = {
        'rev1': {
            'revision': 'rev1',
            'repo_name': 'chromium',
            'commit_position': 1,
            'url': 'url_1'
        },
        'rev2': {
            'revision': 'rev2',
            'repo_name': 'chromium',
            'commit_position': 2,
            'url': 'url_2'
        }
    }
    mock_fn.return_value = culprits_result, ListOfCLKeys()

    culprits = DictOfCLKeys()
    culprits['rev1'] = CLKey(repo_name='chromium', revision='rev1')
    culprits['rev2'] = CLKey(repo_name='chromium', revision='rev2')
    self.MockGeneratorPipeline(
        pipeline_class=RevertAndNotifyTestCulpritPipeline,
        expected_input=CulpritActionParameters(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            culprits=culprits,
            heuristic_cls=ListOfCLKeys()),
        mocked_output=False)

    pipeline = IdentifyTestTryJobCulpritPipeline(master_name, builder_name,
                                                 build_number, '1', test_result)
    pipeline.start()
    self.execute_queued_tasks()

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
            culprits=DictOfCLKeys(),
            heuristic_cls=ListOfCLKeys()),
        mocked_output=False)
    pipeline = IdentifyTestTryJobCulpritPipeline(master_name, builder_name,
                                                 build_number, None, None)
    pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job.test_results, [])
    self.assertEqual(try_job.status, analysis_status.COMPLETED)
