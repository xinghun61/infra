# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import os
import sys
import unittest

import google

from common import rpc_util
from infra_api_clients import logdog_util

from waterfall.test import wf_testcase
from libs.http.retry_http_client import RetryHttpClient

third_party = os.path.join(
  os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.append(os.path.join(third_party, 'google'))
from logdog import annotations_pb2


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
  return json.dumps(data)


_SAMPLE_GET_RESPONSE = _GenerateGetResJson(json.dumps(
  wf_testcase.SAMPLE_STEP_METADATA))

def _CreateProtobufMessage(
    step_name, stdout_stream, step_metadata_stream, label='step_metadata'):
  step = annotations_pb2.Step()
  message = step.substep.add().step
  message.name = step_name
  message.stdout_stream.name = stdout_stream
  link = message.other_links.add(label=label)
  link.logdog_stream.name = step_metadata_stream
  return step


class LogDogUtilTest(unittest.TestCase):
  def setUp(self):
    super(LogDogUtilTest, self).setUp()
    self.http_client = RetryHttpClient()
    self.master_name = 'tryserver.m'
    self.builder_name = 'b'
    self.build_number = 123
    self.step_name = 'browser_tests on platform'
    self.task_id = 'abc123'
    self.stdout_stream = 'stdout_stream'
    self.step_metadata_stream = 'step_metadata_stream'

  def _GenerateTailRes(self):
    step_proto = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream)
    step_log = step_proto.SerializeToString()
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
    return json.dumps(tail_res_json)

  def testProcessStringForLogDog(self):
    builder_name = 'Mac 10.10 Release (Intel)'
    expected_builder_name = 'Mac_10.10_Release__Intel_'
    self.assertEqual(expected_builder_name,
                     logdog_util._ProcessStringForLogDog(builder_name))

  @mock.patch.object(rpc_util, 'DownloadJsonData',
                     return_value=_SAMPLE_GET_RESPONSE)
  def testGetStepMetadataFromLogDog(self, _):
    step_metadata = logdog_util.GetLogForBuild(
      self.master_name, self.builder_name, self.build_number,
      'stream', self.http_client)
    self.assertEqual(json.loads(step_metadata),
                     wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(rpc_util, 'DownloadJsonData',
                     return_value=_SAMPLE_GET_RESPONSE)
  def testGetStepMetadataFromLogDogSwarming(self, _):
    step_metadata = logdog_util.GetLogForSwarmedBuild(
    self.task_id, 'stream', self.http_client)
    self.assertEqual(json.loads(step_metadata),
                     wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(rpc_util, 'DownloadJsonData',
                     return_value=None)
  def testGetStepMetadataFromLogDogNoResponse(self, _):
    step_metadata = logdog_util.GetLogForBuild(
      self.master_name, self.builder_name, self.build_number,
      'stream', self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(rpc_util, 'DownloadJsonData',
                     return_value=json.dumps({'a': 'a'}))
  def testGetStepMetadataFromLogDogNoJson(self, _):
    step_metadata = logdog_util.GetLogForBuild(
      self.master_name, self.builder_name, self.build_number,
      'stream', self.http_client)
    self.assertIsNone(step_metadata)

  def testProcessAnnotationsToGetStreamForStepMetadata(self):
    step_proto = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream)
    log_stream = logdog_util.GetStreamForStep(
      self.step_name, step_proto, 'step_metadata')
    self.assertEqual(log_stream, self.step_metadata_stream)

  def testProcessAnnotationsToGetStreamForStdout(self):
    step_proto = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream)
    log_stream = logdog_util.GetStreamForStep(
      self.step_name, step_proto)
    self.assertEqual(log_stream, self.stdout_stream)

  def testProcessAnnotationsToGetStreamNoStep(self):
    step = _CreateProtobufMessage(
      'step', self.stdout_stream, self.step_metadata_stream)
    log_stream = logdog_util.GetStreamForStep(
      self.step_name, step, 'step_metadata')
    self.assertIsNone(log_stream)

  def testProcessAnnotationsToGetStreamNoStepMetadta(self):
    step = _CreateProtobufMessage(
      self.step_name, self.stdout_stream, self.step_metadata_stream, 'step')
    log_stream = logdog_util.GetStreamForStep(
      self.step_name, step, 'step_metadata')
    self.assertIsNone(log_stream)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProto(self, mock_fn):
    mock_fn.return_value = self._GenerateTailRes()
    step = logdog_util.GetAnnotationsProtoForBuild(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNotNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData', return_value=None)
  def testGetAnnotationsProtoNoResponse(self, _):
    step = logdog_util.GetAnnotationsProtoForBuild(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData',
                     return_value=json.dumps({'a': 'a'}))
  def testGetAnnotationsProtoNoLogs(self, _):
    step = logdog_util.GetAnnotationsProtoForBuild(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData',
                     return_value=json.dumps({'a': 'a'}))
  def testGetAnnotationsProtoNoLogsSwarming(self, _):
    step = logdog_util.GetAnnotationsProtoForSwarmedBuild(
      self.task_id, self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProtoNoAnnotationsB64(self, mock_fn):
    data = {
        'logs': [
            {
                'data': 'data'
            }
        ]
    }
    mock_fn.return_value = json.dumps(data)
    step = logdog_util.GetAnnotationsProtoForBuild(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
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
    mock_fn.return_value = json.dumps(data)
    step = logdog_util.GetAnnotationsProtoForBuild(
      self.master_name, self.builder_name, self.build_number,
      self.http_client)
    self.assertIsNone(step)
