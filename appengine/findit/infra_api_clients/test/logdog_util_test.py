# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging
import mock
import os
import sys
import time
import unittest

import google

from common import rpc_util
from common.findit_http_client import FinditHttpClient
from infra_api_clients import logdog_util
from waterfall.test import wf_testcase

third_party = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, third_party)
google.__path__.append(os.path.join(third_party, 'google'))
from logdog import annotations_pb2


def _GenerateGetResJson(value):
  data = {'logs': [{'text': {'lines': [{'value': value}, {'other': '\n'}]}}]}
  return json.dumps(data)


_SAMPLE_GET_RESPONSE = _GenerateGetResJson(
    json.dumps(wf_testcase.SAMPLE_STEP_METADATA))


def _CreateProtobufMessage(step_name,
                           stdout_stream,
                           step_metadata_stream,
                           label='step_metadata'):
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
    self.http_client = FinditHttpClient()
    self.master_name = 'tryserver.m'
    self.builder_name = 'b'
    self.build_number = 123
    self.step_name = 'browser_tests on platform'
    self.build_data = {
        'result_details_json':
            json.dumps({
                'properties': {
                    'log_location': 'logdog://h/p/path'
                }
            })
    }
    self.stdout_stream = 'stdout_stream'
    self.step_metadata_stream = 'step_metadata_stream'

  def _GenerateTailRes(self):
    step_proto = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                        self.step_metadata_stream)
    step_log = step_proto.SerializeToString()
    step_b64 = base64.b64encode(step_log)
    tail_res_json = {'logs': [{'datagram': {'data': step_b64}}]}
    return json.dumps(tail_res_json)

  def testProcessStringForLogDog(self):
    builder_name = 'Mac 10.10 Release (Intel)'
    expected_builder_name = 'Mac_10.10_Release__Intel_'
    self.assertEqual(expected_builder_name,
                     logdog_util._ProcessStringForLogDog(builder_name))

  def testProcessAnnotationsToGetStreamForStepMetadata(self):
    step_proto = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                        self.step_metadata_stream)
    log_stream = logdog_util._GetStreamForStep(self.step_name, step_proto,
                                               'step_metadata')
    self.assertEqual(log_stream, self.step_metadata_stream)

  def testProcessAnnotationsToGetStreamForStdout(self):
    step_proto = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                        self.step_metadata_stream)
    log_stream = logdog_util._GetStreamForStep(self.step_name, step_proto)
    self.assertEqual(log_stream, self.stdout_stream)

  def testProcessAnnotationsToGetStreamNoStep(self):
    step = _CreateProtobufMessage('step', self.stdout_stream,
                                  self.step_metadata_stream)
    log_stream = logdog_util._GetStreamForStep(self.step_name, step,
                                               'step_metadata')
    self.assertIsNone(log_stream)

  def testProcessAnnotationsToGetStreamNoStepMetadta(self):
    step = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                  self.step_metadata_stream, 'step')
    log_stream = logdog_util._GetStreamForStep(self.step_name, step,
                                               'step_metadata')
    self.assertIsNone(log_stream)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProto(self, mock_fn):
    mock_fn.return_value = (200, self._GenerateTailRes())
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNotNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData', return_value=(500, None))
  def testGetAnnotationsProtoNoResponse(self, _):
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(
      rpc_util, 'DownloadJsonData', return_value=(200, json.dumps({
          'a': 'a'
      })))
  def testGetAnnotationsProtoNoLogs(self, _):
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProtoNoAnnotationsB64(self, mock_fn):
    data = {'logs': [{'data': 'data'}]}
    mock_fn.return_value = (200, json.dumps(data))
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProtoNoB64decodable(self, mock_fn):
    data = {'logs': [{'datagram': {'data': 'data'}}]}
    mock_fn.return_value = (200, json.dumps(data))
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProtoUseGet(self, mock_fn):
    step_proto = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                        self.step_metadata_stream)
    step_log = step_proto.SerializeToString()
    step_log_p1 = step_log[:len(step_log) / 2]
    step_log_p2 = step_log[len(step_log) / 2:]
    data1 = {
        'logs': [{
            'streamIndex': 1,
            'datagram': {
                'data': base64.b64encode(step_log_p2),
                'partial': {
                    'index': 1,
                    'size': 1234
                }
            }
        }]
    }
    data2 = {
        'logs': [{
            'streamIndex': 0,
            'datagram': {
                'data': base64.b64encode(step_log_p1),
                'partial': {
                    'size': 1234
                }
            }
        },
                 {
                     'streamIndex': 1,
                     'datagram': {
                         'data': base64.b64encode(step_log_p2),
                         'partial': {
                             'index': 1,
                             'size': 1234
                         }
                     }
                 }]
    }

    mock_fn.side_effect = [(200, json.dumps(data1)), (200, json.dumps(data2))]
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNotNone(step)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  def testGetAnnotationsProtoGetReturnsNone(self, mock_fn):
    step_proto = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                        self.step_metadata_stream)
    step_log = step_proto.SerializeToString()
    step_log_p2 = step_log[len(step_log) / 2:]
    data1 = {
        'logs': [{
            'streamIndex': 1,
            'datagram': {
                'data': base64.b64encode(step_log_p2),
                'partial': {
                    'index': 1,
                    'size': 1234
                }
            }
        }]
    }

    mock_fn.side_effect = [(200, json.dumps(data1)), (200, None)]
    step = logdog_util._GetAnnotationsProtoForPath('host', 'project', 'path',
                                                   self.http_client)
    self.assertIsNone(step)

  def testGetQueryParametersForAnnotationForBuildbotBuild(self):
    log_location = ('logdog://logs.chromium.org/chromium/bb/m/b/1/+/recipes/'
                    'annotations')
    host, project, path = logdog_util._GetQueryParametersForAnnotation(
        log_location)
    self.assertEqual('logs.chromium.org', host)
    self.assertEqual('chromium', project)
    self.assertEqual('bb/m/b/1/+/recipes/annotations', path)

  def testGetQueryParametersForAnnotationForLUCIBuild(self):
    log_location = ('logdog://logs.chromium.org/chromium/buildbucket/cr-bui'
                    'ldbucket.appspot.com/8948240770002521488/+/annotations')
    host, project, path = logdog_util._GetQueryParametersForAnnotation(
        log_location)
    self.assertEqual('logs.chromium.org', host)
    self.assertEqual('chromium', project)
    self.assertEqual(
        'buildbucket/cr-buildbucket.appspot.com/8948240'
        '770002521488/+/annotations', path)

  def testGetQueryParametersForAnnotationNone(self):
    host, project, path = logdog_util._GetQueryParametersForAnnotation(None)
    self.assertIsNone(host)
    self.assertIsNone(project)
    self.assertIsNone(path)

  @mock.patch.object(rpc_util, 'DownloadJsonData')
  @mock.patch.object(logdog_util, '_GetLog')
  def testGetStepLogLegacy(self, mock_log, mock_data):
    mock_data.return_value = (200, self._GenerateTailRes())
    logdog_util.GetStepLogLegacy('logdog://logdog.com/project/path', 'step',
                                 'stdout', self.http_client)
    self.assertTrue(mock_log.called)

  def testGetStepLogLegacyNoLogLocation(self):
    self.assertIsNone(
        logdog_util.GetStepLogLegacy(None, 'step', 'stdout', self.http_client))

  def testGetLogNoAnnotations(self):
    self.assertIsNone(
        logdog_util._GetLog(None, self.step_name, 'stdout', self.http_client))

  def testGetLogNoStream(self):
    annotations = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                         self.step_metadata_stream)
    self.assertIsNone(
        logdog_util._GetLog(annotations, 'NOT' + self.step_name, 'stdout',
                            self.http_client))

  def testGetLogNoHost(self):
    annotations = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                         self.step_metadata_stream)
    env = annotations.command.environ
    env['LOGDOG_STREAM_PREFIX'] = 'path'
    env['LOGDOG_STREAM_PROJECT'] = 'project'
    self.assertIsNone(
        logdog_util._GetLog(annotations, self.step_name, 'stdout',
                            self.http_client))

  @mock.patch.object(
      FinditHttpClient, 'Get', return_value=(404, None, 'header'))
  @mock.patch.object(logging, 'error')
  def testGetLogRequestFail(self, mock_log, _):
    annotations = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                         self.step_metadata_stream)
    env = annotations.command.environ
    env['LOGDOG_STREAM_PREFIX'] = 'path'
    env['LOGDOG_COORDINATOR_HOST'] = 'logdog.com'
    env['LOGDOG_STREAM_PROJECT'] = 'project'
    self.assertIsNone(
        logdog_util._GetLog(annotations, self.step_name, 'stdout',
                            self.http_client))
    url = ('https://logdog.com/logs/project/path/+/%s?format=raw' %
           self.stdout_stream)
    mock_log.assert_called_once_with(
        'Failed to get the log from %s: status_code-%d, log-%s', url, 404, None)

  @mock.patch.object(FinditHttpClient, 'Get')
  def testGetLog(self, mock_get):
    annotations = _CreateProtobufMessage(self.step_name, self.stdout_stream,
                                         self.step_metadata_stream)
    env = annotations.command.environ
    env['LOGDOG_STREAM_PREFIX'] = 'path'
    env['LOGDOG_COORDINATOR_HOST'] = 'logdog.com'
    env['LOGDOG_STREAM_PROJECT'] = 'project'

    dummy_result = {"a": "b"}
    mock_get.return_value = (200, dummy_result, 'header')
    self.assertEqual(
        dummy_result,
        logdog_util._GetLog(annotations, self.step_name, 'step_metadata',
                            self.http_client))
    mock_get.assert_called_once_with(
        'https://logdog.com/logs/project/path/+/%s?format=raw' %
        self.step_metadata_stream)
