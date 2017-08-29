# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.pipeline_wrapper import pipeline_handlers
from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.test import wf_testcase

FAILURE_INFO = {
    'master_name': 'm',
    'builder_name': 'b',
    'build_number': 123,
    'failed': True,
    'chromium_revision': 'a_git_hash',
    'failed_steps': {
        'abc_test': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123,
        }
    }
}


class ExtractSignalPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

  def testExtractSignalsForTests(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, 'abc_test')
    step.isolated = True
    step.log_data = (
        '{"Unittest2.Subtest1": "RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL3UyczEuY2M6N'
        'TY3OiBGYWlsdXJlCkVSUk9SOlsyXTogMjU5NDczNTAwMCBib2dvLW1pY3Jvc2Vjb25kcw'
        'pFUlJPUjp4X3Rlc3QuY2M6MTIzNAphL2IvdTNzMi5jYzoxMjM6IEZhaWx1cmUK"'
        ', "Unittest3.Subtest2": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCmEvYi91M3My'
        'LmNjOjEyMzogRmFpbHVyZQo="}')
    step.put()

    expected_signals = {
        'abc_test': {
            'files': {
                'a/b/u2s1.cc': [567],
                'a/b/u3s2.cc': [123, 110]
            },
            'keywords': {},
            'tests': {
                'Unittest2.Subtest1': {
                    'files': {
                        'a/b/u2s1.cc': [567],
                        'a/b/u3s2.cc': [123]
                    },
                    'keywords': {}
                },
                'Unittest3.Subtest2': {
                    'files': {
                        'a/b/u3s2.cc': [110, 123]
                    },
                    'keywords': {}
                }
            }
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    pipeline = ExtractSignalPipeline()
    signals = pipeline.run(failure_info)
    self.assertEqual(expected_signals, signals)
