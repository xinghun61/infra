# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import mock

from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from services import extract_signal
from services import step_util
from services.compile_failure import extract_compile_signal
from services.parameters import CompileFailureInfo
from waterfall import waterfall_config
from waterfall.test import wf_testcase

_NINJA_OUTPUT_JSON = json.dumps({
    'failures': [{
        'output_nodes': ['a/b.o'],
        'rule': 'CXX',
        'output': '',
        'dependencies': ['../../b.h', '../../b.c']
    }]
})

_COMPILE_FAILURE_INFO = {
    'master_name': 'm',
    'builder_name': 'b',
    'build_number': 123,
    'failed': True,
    'chromium_revision': 'a_git_hash',
    'failed_steps': {
        'compile': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        }
    }
}


class ExtractCompileSignalTest(wf_testcase.WaterfallTestCase):

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

  @mock.patch.object(
      step_util, 'GetWaterfallBuildStepLog', return_value=_NINJA_OUTPUT_JSON)
  def testGetCompileStepSignalFromNinjaJsonOutput(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_compile_signal.ExtractSignalsForCompileFailure(
        CompileFailureInfo.FromSerializable(_COMPILE_FAILURE_INFO), None)

    expected_failed_edges = [{
        'output_nodes': ['a/b.o'],
        'rule': 'CXX',
        'dependencies': ['b.h', 'b.c']
    }]

    self.assertEqual(expected_failed_edges, signals['compile']['failed_edges'])

  def testCompileStepSignalFromCachedStepLog(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'compile'

    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.log_data = _NINJA_OUTPUT_JSON
    step.put()

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_compile_signal.ExtractSignalsForCompileFailure(
        CompileFailureInfo.FromSerializable(_COMPILE_FAILURE_INFO), None)

    expected_failed_edges = [{
        'output_nodes': ['a/b.o'],
        'rule': 'CXX',
        'dependencies': ['b.h', 'b.c']
    }]

    self.assertEqual(expected_failed_edges, signals['compile']['failed_edges'])

  def testCompileNotSupport(self):
    failure_info = copy.deepcopy(_COMPILE_FAILURE_INFO)
    failure_info['failed_steps']['compile']['supported'] = False
    self.assertEqual({},
                     extract_compile_signal.ExtractSignalsForCompileFailure(
                         CompileFailureInfo.FromSerializable(failure_info),
                         None))

  def testCompileNotInFailedSteps(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 123,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'a': {
                'last_pass': 122,
                'current_failure': 123,
                'first_failure': 123,
            }
        }
    }
    self.assertEqual({},
                     extract_compile_signal.ExtractSignalsForCompileFailure(
                         CompileFailureInfo.FromSerializable(failure_info),
                         None))

  @mock.patch.object(extract_signal, 'GetStdoutLog', return_value=None)
  @mock.patch.object(
      waterfall_config, 'GetDownloadBuildDataSettings', return_value={})
  def testFailedToGetFailureLog(self, *_):
    self.assertEqual(
        {},
        extract_compile_signal.ExtractSignalsForCompileFailure(
            CompileFailureInfo.FromSerializable(_COMPILE_FAILURE_INFO), None))
