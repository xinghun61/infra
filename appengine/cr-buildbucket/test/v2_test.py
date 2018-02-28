# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from components import utils
utils.fix_protobuf_package()

from google.protobuf import json_format
from google.protobuf import struct_pb2
from google.protobuf import timestamp_pb2

from components import auth
from testing_utils import testing

from proto import common_pb2
from proto import build_pb2
import model
import v2


class V2Test(testing.AppengineTestCase):
  def test_get_builder_id(self):
    build = model.Build(
        project='chromium',
        bucket='master.tryserver.chromium.linux',
        parameters={
          v2.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
    )
    self.assertEqual(
        v2._get_builder_id(build),
        build_pb2.Builder.ID(
            project='chromium',
            bucket='master.tryserver.chromium.linux',
            builder='linux_chromium_rel_ng',
        ))

  def test_get_builder_id_luci(self):
    build = model.Build(
        project='chromium',
        bucket='luci.chromium.try',
        parameters={
          v2.BUILDER_PARAMETER: 'linux-rel',
        },
    )
    self.assertEqual(
        v2._get_builder_id(build),
        build_pb2.Builder.ID(
            project='chromium',
            bucket='try',
            builder='linux-rel',
        ))

  def test_get_status(self):
    cases = [
      (common_pb2.SCHEDULED, model.Build()),
      (common_pb2.STARTED, model.Build(status=model.BuildStatus.STARTED)),
      (common_pb2.SUCCESS, model.Build(
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.SUCCESS)),
      (common_pb2.FAILURE, model.Build(
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.FAILURE,
          failure_reason=model.FailureReason.BUILD_FAILURE)),
      (common_pb2.INFRA_FAILURE, model.Build(
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.FAILURE)),
      (common_pb2.INFRA_FAILURE, model.Build(
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.FAILURE,
          failure_reason=model.FailureReason.INFRA_FAILURE)),
      (common_pb2.CANCELED, model.Build(
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.CANCELED,
          cancelation_reason=model.CancelationReason.CANCELED_EXPLICITLY)),
      (common_pb2.INFRA_FAILURE, model.Build(
          status=model.BuildStatus.COMPLETED,
          result=model.BuildResult.CANCELED,
          cancelation_reason=model.CancelationReason.TIMEOUT)),
    ]
    for expected_status, build in cases:
       self.assertEqual(
          v2._get_status(build),
          expected_status,
          msg='%r' % build,
      )

  def test_build_to_v2(self):
    dt0 = datetime.datetime(2018, 1, 1, 0)
    ts0 = timestamp_pb2.Timestamp(seconds=1514764800)

    dt1 = datetime.datetime(2018, 1, 1, 1)
    ts1 = timestamp_pb2.Timestamp(seconds=1514768400)

    dt2 = datetime.datetime(2018, 1, 1, 2)
    ts2 = timestamp_pb2.Timestamp(seconds=1514772000)

    input_properties = {
      'str': 'a',
      'num': 1,
      'obj': {
        'str': 'b',
      },
      'arr': [1, 2],
    }
    output_properties = {'x': 1}
    build = mkbuild(
        create_time=dt0,
        start_time=dt1,
        complete_time=dt2,
        update_time=dt2,
        tags=[
          'a:b',
          'buildset:bs',
          'swarming_dimension:os:Ubuntu',
          'swarming_dimension:pool:luci.chromium.try',
          ('swarming_tag:buildbucket_template_revision:'
           '8f8d0f72e3689c4e4a943c52a8805c24563c8b2d'),
          'swarming_tag:priority:100',
        ],
        status=model.BuildStatus.COMPLETED,
        result=model.BuildResult.SUCCESS,
        parameters={
          'properties': input_properties,
        },
        result_details={
          'properties': output_properties,
          'swarming': {
            'task_result': {
              'bot_dimensions': [
                { 'key': 'os', 'value': ['Ubuntu', 'Trusty'] },
                { 'key': 'pool', 'value': ['luci.chromium.try'] },
                { 'key': 'id', 'value': ['bot1'] },
              ],
            }
          }
        },
        experimental=True,

        swarming_hostname='swarming.example.com',
        swarming_task_id='deadbeef',
        service_account='service-account@example.com',

        url='https://ci.example.com/build',
    )

    expected = build_pb2.Build(
        id=1,
        builder=build_pb2.Builder.ID(
            project='chromium',
            bucket='try',
            builder='linux-rel',
        ),
        number=0,
        create_time=ts0,
        start_time=ts1,
        end_time=ts2,
        update_time=ts2,
        status=common_pb2.SUCCESS,
        tags=[
          common_pb2.StringPair(key='a', value='b'),
          common_pb2.StringPair(key='buildset', value='bs'),
        ],
        input=build_pb2.Build.Input(
          properties=v2._dict_to_struct(input_properties),
          experimental=True,
        ),
        output=build_pb2.Build.Output(
            properties=v2._dict_to_struct(output_properties),
        ),
        infra=build_pb2.BuildInfra(
          buildbucket=build_pb2.BuildInfra.Buildbucket(
              service_config_revision=(
                  '8f8d0f72e3689c4e4a943c52a8805c24563c8b2d'),
              canary=False,
          ),
          swarming=build_pb2.BuildInfra.Swarming(
              hostname='swarming.example.com',
              task_id='deadbeef',
              task_service_account='service-account@example.com',
              priority=100,
              task_dimensions=[
                common_pb2.StringPair(key='os', value='Ubuntu'),
                common_pb2.StringPair(key='pool', value='luci.chromium.try'),
              ],
              bot_dimensions=[
                common_pb2.StringPair(key='os', value='Ubuntu'),
                common_pb2.StringPair(key='os', value='Trusty'),
                common_pb2.StringPair(key='pool', value='luci.chromium.try'),
                common_pb2.StringPair(key='id', value='bot1'),
              ],
          ),
        ),

        created_by='user:john@example.com',
        view_url='https://ci.example.com/build',
    )
    # Compare messages as dicts.
    # assertEqual has better support for dicts.
    self.assertEqual(
        msg_to_dict(expected),
        msg_to_dict(v2.build_to_v2(build)))

  def test_build_to_v2_number(self):
    build = mkbuild(
        result_details={
          'properties': {'buildnumber': 54},
        },
    )
    msg = v2.build_to_v2(build)
    self.assertEqual(msg.number, 54)

  def test_build_to_changes(self):
    build = mkbuild(
        tags=[
          'buildset:x',
          ('buildset:commit/gitiles/chromium.googlesource.com/'
           'infra/luci/luci-go/+/b7a757f457487cd5cfe2dae83f65c5bc10e288b7'),
          ('buildset:patch/gerrit/chromium-review.googlesource.com/677784/5'),
        ],
    )
    msg = v2.build_to_v2(build)
    self.assertEqual(list(msg.tags), [common_pb2.StringPair(
        key='buildset',
        value='x',
    )])
    self.assertEqual(list(msg.input.gitiles_commits), [common_pb2.GitilesCommit(
        host='chromium.googlesource.com',
        project='infra/luci/luci-go',
        id='b7a757f457487cd5cfe2dae83f65c5bc10e288b7',
    )])
    self.assertEqual(list(msg.input.gerrit_changes), [common_pb2.GerritChange(
        host='chromium-review.googlesource.com',
        change=677784,
        patchset=5,
    )])

  def test_build_to_v2_invalid_priority(self):
    build = mkbuild(
        tags=['swarming_tag:priority:blah'],
    )
    msg = v2.build_to_v2(build)
    self.assertEqual(msg.infra.swarming.priority, 0)
    self.assertEqual(list(msg.tags), [common_pb2.StringPair(
      key='swarming_tag',
      value='priority:blah',
    )])

  def test_build_to_v2_no_builder_name(self):
    build = mkbuild()
    del build.parameters[v2.BUILDER_PARAMETER]
    with self.assertRaises(v2.UnsupportedBuild):
      v2.build_to_v2(build)


def mkbuild(**kwargs):
  args = dict(
      id=1,
      project='chromium',
      bucket='luci.chromium.try',
      parameters={v2.BUILDER_PARAMETER: 'linux-rel'},
      created_by=auth.Identity('user', 'john@example.com'),
  )
  args['parameters'].update(kwargs.pop('parameters', {}))
  args.update(kwargs)
  return model.Build(**args)


def msg_to_dict(message):
  return json.loads(json_format.MessageToJson(message))
