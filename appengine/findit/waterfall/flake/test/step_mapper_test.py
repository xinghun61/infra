# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import os
import sys

import google

from gae_libs.http.http_client_appengine import HttpClientAppengine
from model.flake.flake_analysis_request import BuildStep
from waterfall import buildbot
from waterfall import swarming_util
from waterfall.flake import step_mapper
from waterfall.test import wf_testcase

third_party = os.path.join(
    os.path.dirname(__file__), os.path.pardir,os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.append(os.path.join(third_party, 'google'))
from logdog import annotations_pb2


_SAMPLE_STEP_METADATA = {
    'waterfall_mastername': 'm',
    'waterfall_buildername': 'b',
    'canonical_step_name': 'browser_tests',
    'full_step_name': 'browser_tests on platform',
    'dimensions': {
        'os': 'platform'
    },
    'swarm_task_ids': ['1000']
}


_SAMPLE_STEP_METADATA_NOT_SWARMED = {
    'waterfall_mastername': 'm',
    'waterfall_buildername': 'b',
    'canonical_step_name': 'browser_tests',
    'full_step_name': 'browser_tests on platform',
    'dimensions': {
        'os': 'platform'
    }
}


_SAMPLE_OUTPUT = {
    'all_tests': ['test1'],
    'per_iteration_data': [
        {
            'is_dict': True
        }
    ]
}


def _GenerateGetResJson(value):
  data = {
      'logs': [
          {
              'text': {
                  'lines': [
                      {
                          'value': value
                      },
                      {
                          'other': '\n'
                      }
                  ]
              }
          }
      ]
  }
  return data


_SAMPLE_GET_RESPONSE = _GenerateGetResJson(json.dumps(_SAMPLE_STEP_METADATA))


def _CreateProtobufMessage(step_name, label, stream_name):
  step = annotations_pb2.Step()
  message = step.substep.add().step
  message.name = step_name
  link = message.other_links.add(label=label)
  link.logdog_stream.name = stream_name
  return step


def _GenerateTailRes(step_name, label, stream_name):
  step = _CreateProtobufMessage(step_name, label, stream_name)
  step_log = step.SerializeToString()
  step_b64 = base64.b64encode(step_log)
  tail_res_json = {
      'logs': [
          {
              'datagram': {
                  'data': step_b64
              }
          }
      ]
  }
  return tail_res_json


class StepMapperTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(StepMapperTest, self).setUp()
    self.http_client = HttpClientAppengine()
    self.master_name = 'tryserver.m'
    self.wf_master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 123
    self.step_name = 'browser_tests on platform'
    self.build_step = BuildStep.Create(
        self.master_name, self.builder_name, self.build_number,
        self.step_name, None)
    self.build_step.put()

    self.wf_build_step = BuildStep.Create(
        self.wf_master_name, self.builder_name, self.build_number,
        self.step_name, None)
    self.wf_build_step.put()

  @mock.patch.object(step_mapper, '_GetMatchingWaterfallBuildStep',
                     return_value=('tryserver.m', 'b', 123, 'browser_tests',
                                   _SAMPLE_STEP_METADATA))
  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask',
                     return_value=_SAMPLE_OUTPUT)
  def testFindMatchingWaterfallStep(self, *_):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertTrue(self.build_step.swarmed)
    self.assertTrue(self.build_step.supported)

  @mock.patch.object(step_mapper, '_GetMatchingWaterfallBuildStep',
                     return_value=('tryserver.m', None, 123, 'browser_tests',
                                   _SAMPLE_STEP_METADATA))
  def testFindMatchingWaterfallStepNoMatch(self, _):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertFalse(self.build_step.swarmed)
    self.assertIsNone(self.build_step.wf_builder_name)

  @mock.patch.object(step_mapper, '_GetMatchingWaterfallBuildStep',
                     return_value=('tryserver.m', 'b', 123, 'browser_tests',
                                   _SAMPLE_STEP_METADATA_NOT_SWARMED))
  def testFindMatchingWaterfallStepNotSwarmed(self, _):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertFalse(self.build_step.swarmed)

  @mock.patch.object(step_mapper, '_GetMatchingWaterfallBuildStep',
                     return_value=('tryserver.m', 'b', 123, 'browser_tests',
                                   _SAMPLE_STEP_METADATA))
  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask',
                     return_value=None)
  def testFindMatchingWaterfallStepNoOutput(self, *_):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertTrue(self.build_step.swarmed)
    self.assertFalse(self.build_step.supported)

  def testProcessStringForLogDog(self):
    builder_name = 'Mac 10.10 Release (Intel)'
    expected_builder_name = 'Mac_10.10_Release__Intel_'
    self.assertEqual(expected_builder_name,
                     step_mapper._ProcessStringForLogDog(builder_name))

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value=_SAMPLE_GET_RESPONSE)
  def testGetStepMetadataFromLogDog(self, _):
    step_metadata = step_mapper._GetStepMetadataFromLogDog(
        self.build_step, 'stream', self.http_client)
    self.assertEqual(step_metadata, _SAMPLE_STEP_METADATA)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetStepMetadataFromLogDogMalFormated(self, mock_fn):
    mock_fn.return_value = _GenerateGetResJson('data')
    step_metadata = step_mapper._GetStepMetadataFromLogDog(
        self.build_step, 'stream', self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value=None)
  def testGetStepMetadataFromLogDogNoResponse(self, _):
    step_metadata = step_mapper._GetStepMetadataFromLogDog(
        self.build_step, 'stream', self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(buildbot, 'DownloadJsonData',
                     return_value={'a': 'a'})
  def testGetStepMetadataFromLogDogNoJson(self, _):
    step_metadata = step_mapper._GetStepMetadataFromLogDog(
        self.build_step, 'stream', self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(step_mapper, '_GetAnnotationsProto',
                     return_value='step')
  @mock.patch.object(step_mapper, '_ProcessAnnotationsToGetStream',
                     return_value='log_stream')
  @mock.patch.object(step_mapper, '_GetStepMetadataFromLogDog',
                     return_value=_SAMPLE_STEP_METADATA)
  def testGetStepMetadata(self, *_):
    step_metadata = step_mapper._GetStepMetadata(
        self.build_step, self.http_client)
    self.assertEqual(step_metadata, _SAMPLE_STEP_METADATA)

  @mock.patch.object(step_mapper, '_GetAnnotationsProto',
                     return_value=None)
  def testGetStepMetadataStepNone(self, _):
    step_metadata = step_mapper._GetStepMetadata(
        self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(step_mapper, '_GetAnnotationsProto',
                     return_value='step')
  @mock.patch.object(step_mapper, '_ProcessAnnotationsToGetStream',
                     return_value=None)
  def testGetStepMetadataStreamNone(self, *_):
    step_metadata = step_mapper._GetStepMetadata(
        self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(step_mapper, '_GetStepMetadata',
                     return_value=_SAMPLE_STEP_METADATA)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds',
                     return_value=[123])
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags',
                     return_value=[{'tags': [
                         'stepname:browser_tests on platform']}])
  def testGetMatchingWaterfallBuildStep(self, *_):
    master_name, builder_name, build_number, step_name, step_metadata = (
        step_mapper._GetMatchingWaterfallBuildStep(
            self.build_step, self.http_client))
    self.assertEqual(master_name, self.wf_master_name)
    self.assertEqual(builder_name, self.builder_name)
    self.assertEqual(build_number, self.build_number)
    self.assertEqual(step_name, self.step_name)
    self.assertEqual(step_metadata, _SAMPLE_STEP_METADATA)

  @mock.patch.object(step_mapper, '_GetStepMetadata', return_value=None)
  def testGetMatchingWaterfallBuildStepNoMetadata(self, _):
    _, _, _, _, step_metadata = step_mapper._GetMatchingWaterfallBuildStep(
         self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(step_mapper, '_GetStepMetadata')
  def testGetMatchingWaterfallBuildStepNoWfBuilderName(self, mock_fn):
    mock_fn.return_value = {
        'waterfall_mastername': self.wf_master_name
    }
    _, _, _, _, step_metadata = step_mapper._GetMatchingWaterfallBuildStep(
         self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(step_mapper, '_GetStepMetadata')
  def testGetMatchingWaterfallBuildStepNoStep(self, mock_fn):
    mock_fn.return_value = {
        'waterfall_mastername': self.wf_master_name,
        'waterfall_buildername': 'b'
    }
    _, _, _, _, step_metadata = step_mapper._GetMatchingWaterfallBuildStep(
         self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(step_mapper, '_GetStepMetadata',
                     return_value=_SAMPLE_STEP_METADATA)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds',
                     return_value=None)
  def testGetMatchingWaterfallBuildStepNoBuild(self, *_):
    master_name, _, _, _, _ = step_mapper._GetMatchingWaterfallBuildStep(
         self.build_step, self.http_client)
    self.assertIsNone(master_name)

  @mock.patch.object(step_mapper, '_GetStepMetadata',
                     return_value=_SAMPLE_STEP_METADATA)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds',
                     return_value=[123])
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags',
                     return_value=None)
  def testGetMatchingWaterfallBuildStepNoTask(self, *_):
    master_name, _, _, _, _ = step_mapper._GetMatchingWaterfallBuildStep(
         self.build_step, self.http_client)
    self.assertIsNone(master_name)

  def testProcessAnnotationsToGetStream(self):
    stream = 'stream'
    step = _CreateProtobufMessage(self.step_name, 'step_metadata', stream)
    log_stream = step_mapper._ProcessAnnotationsToGetStream(
        self.build_step, step)
    self.assertEqual(log_stream, stream)

  def testProcessAnnotationsToGetStreamNoStep(self):
    stream = 'stream'
    step = _CreateProtobufMessage('step', 'step_metadata', stream)
    log_stream = step_mapper._ProcessAnnotationsToGetStream(
        self.build_step, step)
    self.assertIsNone(log_stream)

  def testProcessAnnotationsToGetStreamNoStepMetadta(self):
    stream = 'stream'
    step = _CreateProtobufMessage(self.step_name, 'step', stream)
    log_stream = step_mapper._ProcessAnnotationsToGetStream(
        self.build_step, step)
    self.assertIsNone(log_stream)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsProto(self, mock_fn):
    mock_fn.return_value = _GenerateTailRes(
        self.step_name, 'step_metadata', 'stream')
    step = step_mapper._GetAnnotationsProto(self.build_step, self.http_client)
    self.assertIsNotNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData', return_value=None)
  def testGetAnnotationsProtoNoResponse(self, _):
    step = step_mapper._GetAnnotationsProto(self.build_step, self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData', return_value={'a':'a'})
  def testGetAnnotationsProtoNoLogs(self, _):
    step = step_mapper._GetAnnotationsProto(self.build_step, self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsProtoNoAnnotationsB64(self, mock_fn):
    data = {
        'logs': [
            {
                'data': 'data'
            }
        ]
    }
    mock_fn.return_value = data
    step = step_mapper._GetAnnotationsProto(self.build_step, self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsProtoNoB64decodable(self, mock_fn):
    data = {
        'logs': [
            {
                'datagram': {
                    'data': 'data'
                }
            }
        ]
    }
    mock_fn.return_value = data
    step = step_mapper._GetAnnotationsProto(self.build_step, self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(buildbot, 'DownloadJsonData')
  def testGetAnnotationsTailReturnedEmpty(self, mock_fn):
    data = {
        'logs': [
            {
                'datagram': {
                    'data': 'data'
                }
            }
        ]
    }
    mock_fn.side_effect = [{}, data]
    step = step_mapper._GetAnnotationsProto(self.build_step, self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask',
                     return_value=_SAMPLE_OUTPUT)
  @mock.patch.object(swarming_util, 'ListSwarmingTasksDataByTags',
                     return_value=[{'tags': [
                         'stepname:browser_tests on platform']}])
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds',
                     return_value=[123])
  @mock.patch.object(step_mapper, '_GetStepMetadataFromLogDog',
                     return_value=_SAMPLE_STEP_METADATA)
  @mock.patch.object(step_mapper, '_GetAnnotationsProto')
  def testFindMatchingWaterfallStepEndToEnd(self, mock_fn, *_):
    stream = 'stream'
    step = _CreateProtobufMessage(self.step_name, 'step_metadata', stream)
    mock_fn.return_value = step
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertTrue(self.build_step.swarmed)
    self.assertTrue(self.build_step.supported)

  @mock.patch.object(step_mapper, '_GetStepMetadata',
                     return_value={})
  def testFindMatchingWaterfallStepForWfStepNoStepMetadata(self, _):
    step_mapper.FindMatchingWaterfallStep(self.wf_build_step, 'test1')
    self.assertEqual(self.wf_build_step.wf_build_number,
                     self.wf_build_step.build_number)
    self.assertFalse(self.wf_build_step.swarmed)
    self.assertFalse(self.wf_build_step.supported)

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask',
                     return_value=_SAMPLE_OUTPUT)
  @mock.patch.object(step_mapper, '_GetStepMetadata',
                     return_value=_SAMPLE_STEP_METADATA)
  def testFindMatchingWaterfallStepForWfStep(self, *_):
    step_mapper.FindMatchingWaterfallStep(self.wf_build_step, 'test1')
    self.assertTrue(self.wf_build_step.swarmed)
    self.assertTrue(self.wf_build_step.supported)