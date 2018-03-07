# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import datetime
import json

from components import utils
utils.fix_protobuf_package()

from google.protobuf import json_format

from components import net
from testing_utils import testing

from proto import common_pb2
from proto import step_pb2
from test import test_util
from third_party import annotations_pb2
from v2 import errors
from v2 import steps
import model


class V2StepsTest(testing.AppengineTestCase):
  def test_get_annotation_url(self):
    url = (
        'logdog://luci-logdog-dev.appspot.com/'
        'infra/'
        'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048/+/'
        'annotations')
    build = model.Build(
        id=1,
        swarming_task_id='deadbeef',
        tags=[
          'unrelated:1',
          'swarming_tag:log_location:' + url,
        ],
    )
    actual = steps._get_annotation_url(build)
    self.assertEqual(actual, url)

  def test_parse_logdog_url(self):
    url = (
        'logdog://luci-logdog-dev.appspot.com/'
        'infra/'
        'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048/+/'
        'annotations')
    expected = (
      'luci-logdog-dev.appspot.com',
      'infra',
      'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048',
      'annotations',
    )
    actual = steps._parse_logdog_url(url)
    self.assertEqual(actual, expected)


class FetchStepsTest(testing.AppengineTestCase):
  def setUp(self):
    super(FetchStepsTest, self).setUp()

    url = (
      'logdog://luci-logdog-dev.appspot.com/'
      'infra/'
      'buildbucket/cr-buildbucket-dev.appspot.com/8952867341410234048/+/'
      'annotations')
    self.test_build = model.Build(
        id=1,
        swarming_task_id='deadbeef',
        tags=[
          'swarming_tag:log_location:' + url,
        ],
    )
    self.allowed_logdog_hosts = ['luci-logdog-dev.appspot.com']

    self.patch('components.net.json_request_async', autospec=True)

    self.ann_step = annotations_pb2.Step(
      substep=[
        annotations_pb2.Step.Substep(
          step=annotations_pb2.Step(
            name='step0',
            status=annotations_pb2.SUCCESS,
          ),
        ),
      ],
    )
    self.v2_steps = [
      step_pb2.Step(name='step0', status=common_pb2.SUCCESS),
    ]

  def test_no_logdog_url(self):
    net.json_request_async.side_effect = AssertionError
    build = model.Build(id=1)

    res, finalized = steps.fetch_steps_async(
        build, self.allowed_logdog_hosts).get_result()
    self.assertEqual(res, [])
    self.assertTrue(finalized)

  def test_no_logdog_url_swarmbucket(self):
    net.json_request_async.side_effect = AssertionError
    build = model.Build(id=1, swarming_task_id='deadbeef')

    with self.assertRaises(errors.MalformedBuild):
      steps.fetch_steps_async(build, self.allowed_logdog_hosts).get_result()

  def test_invalid_logdog_url(self):
    net.json_request_async.side_effect = AssertionError
    build = model.Build(
        id=1,
        swarming_task_id='deadbeef',
        tags=[
          'swarming_tag:log_location:invalid',
        ],
    )

    with self.assertRaises(errors.MalformedBuild):
      steps.fetch_steps_async(build, self.allowed_logdog_hosts).get_result()

  def test_not_whitelisted_logdog_host(self):
    net.json_request_async.side_effect = AssertionError
    result, finalized = steps.fetch_steps_async(
        self.test_build, []).get_result()
    self.assertEquals(len(result), 0)
    self.assertTrue(finalized)

  def test_not_found(self):
    net.json_request_async.side_effect = net.NotFoundError('no', 404, None)

    actual, finalized = steps.fetch_steps_async(
        self.test_build, self.allowed_logdog_hosts).get_result()
    self.assertEqual(actual, [])
    self.assertFalse(finalized)

  def test_net_error(self):
    net.json_request_async.side_effect = net.Error('boom', 500, None)

    with self.assertRaises(errors.StepFetchError):
      steps.fetch_steps_async(
          self.test_build, self.allowed_logdog_hosts).get_result()

  def test_no_terminal_log(self):
    net.json_request_async.return_value = test_util.future({
      'state': {
        'terminalIndex': 100,
      },
      'logs': [
        {
          'sequence': 99,
          'datagram': {
            'data': base64.b64encode(self.ann_step.SerializeToString())
          },
        },
      ],
    })

    actual, finalized = steps.fetch_steps_async(
        self.test_build, self.allowed_logdog_hosts).get_result()
    self.assertEqual(
        map(test_util.msg_to_dict, actual),
        map(test_util.msg_to_dict, self.v2_steps),
    )
    self.assertFalse(finalized)

  def test_no_terminator(self):
    net.json_request_async.return_value = test_util.future({
      'state': {
        'terminalIndex': -1,
      },
      'logs': [
        {
          'sequence': 1,
          'datagram': {
            'data': base64.b64encode(self.ann_step.SerializeToString())
          },
        },
      ],
    })

    actual, finalized = steps.fetch_steps_async(
        self.test_build, self.allowed_logdog_hosts).get_result()
    self.assertEqual(
        map(test_util.msg_to_dict, actual),
        map(test_util.msg_to_dict, self.v2_steps),
    )
    self.assertFalse(finalized)

  def test_success(self):
    net.json_request_async.return_value = test_util.future({
      'state': {
        'terminalIndex': 100,
      },
      'logs': [
        {
          'sequence': 100,
          'datagram': {
            'data': base64.b64encode(self.ann_step.SerializeToString())
          }
        }
      ]
    })

    actual, finalized = steps.fetch_steps_async(
        self.test_build, self.allowed_logdog_hosts).get_result()
    self.assertEqual(
        map(test_util.msg_to_dict, actual),
        map(test_util.msg_to_dict, self.v2_steps),
    )
    self.assertTrue(finalized)
