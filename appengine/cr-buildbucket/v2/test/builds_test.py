# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from components import utils
utils.fix_protobuf_package()

from google.protobuf import timestamp_pb2

from components import auth

from proto import common_pb2
from proto import build_pb2
from v2 import builds
from test import test_util
import model


class V2BuildsTest(unittest.TestCase):
  max_diff = None

  def test_get_builder_id(self):
    build = model.Build(
        project='chromium',
        bucket='master.tryserver.chromium.linux',
        parameters={
            model.BUILDER_PARAMETER: 'linux_chromium_rel_ng',
        },
    )
    self.assertEqual(
        builds._get_builder_id(build),
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
            model.BUILDER_PARAMETER: 'linux-rel',
        },
    )
    self.assertEqual(
        builds._get_builder_id(build),
        build_pb2.Builder.ID(
            project='chromium',
            bucket='try',
            builder='linux-rel',
        ))

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
        tags=['a:b', 'c:d'],
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
                        {
                            'key': 'os',
                            'value': ['Ubuntu', 'Trusty']
                        },
                        {
                            'key': 'pool',
                            'value': ['luci.chromium.try']
                        },
                        {
                            'key': 'id',
                            'value': ['bot1']
                        },
                    ],
                }
            }
        },
        experimental=True,
        swarming_hostname='swarming.example.com',
        swarming_task_id='deadbeef',
        service_account='service-account@example.com',
        logdog_hostname='logs.chromium.org',
        logdog_project='chromium',
        logdog_prefix='buildbucket/cr-buildbucket.example.com/81271231ba012',
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
            common_pb2.StringPair(key='c', value='d'),
        ],
        input=build_pb2.Build.Input(
            properties=builds._dict_to_struct(input_properties),
            experimental=True,
        ),
        output=build_pb2.Build.Output(
            properties=builds._dict_to_struct(output_properties),),
        infra=build_pb2.BuildInfra(
            buildbucket=build_pb2.BuildInfra.Buildbucket(canary=False,),
            swarming=build_pb2.BuildInfra.Swarming(
                hostname='swarming.example.com',
                task_id='deadbeef',
                task_service_account='service-account@example.com',
                bot_dimensions=[
                    common_pb2.StringPair(key='os', value='Ubuntu'),
                    common_pb2.StringPair(key='os', value='Trusty'),
                    common_pb2.StringPair(
                        key='pool', value='luci.chromium.try'),
                    common_pb2.StringPair(key='id', value='bot1'),
                ],
            ),
            logdog=build_pb2.BuildInfra.LogDog(
                hostname='logs.chromium.org',
                project='chromium',
                prefix='buildbucket/cr-buildbucket.example.com/81271231ba012',
            ),
        ),
        created_by='user:john@example.com',
    )
    # Compare messages as dicts.
    # assertEqual has better support for dicts.
    self.assertEqual(
        test_util.msg_to_dict(expected),
        test_util.msg_to_dict(builds.build_to_v2_partial(build)))

  def test_build_to_v2_number_in_result_details(self):
    msg = builds.build_to_v2_partial(
        mkbuild(result_details={
            'properties': {
                'buildnumber': 54
            },
        },))
    self.assertEqual(msg.number, 54)

  def test_parse_tags(self):
    tags = [
        'builder:excluded',
        'buildset:bs',
        ('buildset:commit/gitiles/chromium.googlesource.com/'
         'infra/luci/luci-go/+/b7a757f457487cd5cfe2dae83f65c5bc10e288b7'),
        ('buildset:patch/gerrit/chromium-review.googlesource.com/677784/5'),
        'swarming_dimension:os:Ubuntu',
        'swarming_dimension:pool:luci.chromium.try',
        ('swarming_tag:buildbucket_template_revision:'
         '8f8d0f72e3689c4e4a943c52a8805c24563c8b2d'),
        ('swarming_tag:excluded:1'),
        'swarming_tag:priority:100',
        'build_address:bucket/builder/1',
        'swarming_hostname:swarming.example.com',
        'swarming_task_id:deadbeef',
    ]

    expected = build_pb2.Build(
        number=1,
        tags=[
            common_pb2.StringPair(key='buildset', value='bs'),
        ],
        input=build_pb2.Build.Input(
            gitiles_commit=common_pb2.GitilesCommit(
                host='chromium.googlesource.com',
                project='infra/luci/luci-go',
                id='b7a757f457487cd5cfe2dae83f65c5bc10e288b7',
            ),
            gerrit_changes=[
                common_pb2.GerritChange(
                    host='chromium-review.googlesource.com',
                    change=677784,
                    patchset=5,
                ),
            ],
        ),
        infra=build_pb2.BuildInfra(
            buildbucket=build_pb2.BuildInfra.Buildbucket(
                service_config_revision=(
                    '8f8d0f72e3689c4e4a943c52a8805c24563c8b2d'),),
            swarming=build_pb2.BuildInfra.Swarming(
                priority=100,
                task_dimensions=[
                    common_pb2.StringPair(key='os', value='Ubuntu'),
                    common_pb2.StringPair(
                        key='pool', value='luci.chromium.try'),
                ],
            ),
        ),
    )

    actual = build_pb2.Build()
    builds._parse_tags(actual, tags)
    # Compare messages as dicts.
    # assertEqual has better support for dicts.
    self.assertEqual(
        test_util.msg_to_dict(expected), test_util.msg_to_dict(actual))

  def test_build_to_v2_invalid_priority(self):
    build = mkbuild(tags=['swarming_tag:priority:blah'],)
    msg = builds.build_to_v2_partial(build)
    self.assertEqual(msg.infra.swarming.priority, 0)
    self.assertEqual(len(msg.tags), 0)

  def test_build_to_v2_no_builder_name(self):
    build = mkbuild()
    del build.parameters[model.BUILDER_PARAMETER]
    with self.assertRaises(builds.UnsupportedBuild):
      builds.build_to_v2_partial(build)

  def test_two_gitiles_commits(self):
    build = mkbuild(tags=[
        ('buildset:commit/gitiles/chromium.googlesource.com/'
         'infra/luci/luci-go/+/b7a757f457487cd5cfe2dae83f65c5bc10e288b7'),
        ('buildset:commit/gitiles/chromium.googlesource.com/'
         'infra/luci/luci-go/+/b7a757f457487cd5cfe2dae83f65c5bc10e288b8'),
    ])
    err_pattern = r'more than one commits/gitiles/ buildset'
    with self.assertRaisesRegexp(builds.MalformedBuild, err_pattern):
      builds.build_to_v2_partial(build)


class TestStatusConversion(unittest.TestCase):
  def compare(self, build_v1, build_v2, test_to_v1=True):
    actual_v2 = build_pb2.Build()
    builds.status_to_v2(build_v1, actual_v2)
    self.assertEqual(actual_v2, build_v2)

    if not test_to_v1:
      return

    actual_v1 = model.Build()
    builds.status_to_v1(build_v2, actual_v1)
    self.assertEqual(actual_v1.status, build_v1.status)
    self.assertEqual(actual_v1.result, build_v1.result)
    self.assertEqual(actual_v1.failure_reason, build_v1.failure_reason)
    self.assertEqual(actual_v1.cancelation_reason, build_v1.cancelation_reason)

  def test_empty(self):
    self.compare(
        model.Build(),
        build_pb2.Build(status=common_pb2.SCHEDULED))

  def test_started(self):
    self.compare(
        model.Build(status=model.BuildStatus.STARTED),
        build_pb2.Build(status=common_pb2.STARTED))

  def test_success(self):
    self.compare(
        model.Build(
            status=model.BuildStatus.COMPLETED,
            result=model.BuildResult.SUCCESS),
        build_pb2.Build(status=common_pb2.SUCCESS))

  def test_build_failure(self):
    self.compare(
        model.Build(
            status=model.BuildStatus.COMPLETED,
            result=model.BuildResult.FAILURE,
            failure_reason=model.FailureReason.BUILD_FAILURE),
        build_pb2.Build(status=common_pb2.FAILURE))

  def test_generic_failure(self):
    self.compare(
        model.Build(
            status=model.BuildStatus.COMPLETED,
            result=model.BuildResult.FAILURE),
        build_pb2.Build(
            status=common_pb2.INFRA_FAILURE,
            infra_failure_reason=build_pb2.InfraFailureReason(
                resource_exhaustion=False,
            )),
        test_to_v1=False)

  def test_infra_failure(self):
    self.compare(
        model.Build(
            status=model.BuildStatus.COMPLETED,
            result=model.BuildResult.FAILURE,
            failure_reason=model.FailureReason.INFRA_FAILURE),
        build_pb2.Build(
            status=common_pb2.INFRA_FAILURE,
            infra_failure_reason=build_pb2.InfraFailureReason(
                resource_exhaustion=False,
            )))

  def test_canceled(self):
    self.compare(
        model.Build(
            status=model.BuildStatus.COMPLETED,
            result=model.BuildResult.CANCELED,
            cancelation_reason=model.CancelationReason.CANCELED_EXPLICITLY),
        build_pb2.Build(status=common_pb2.CANCELED))

  def test_timeout(self):
    self.compare(
        model.Build(
            status=model.BuildStatus.COMPLETED,
            result=model.BuildResult.CANCELED,
            cancelation_reason=model.CancelationReason.TIMEOUT),
        build_pb2.Build(
            status=common_pb2.INFRA_FAILURE,
            infra_failure_reason=build_pb2.InfraFailureReason(
                resource_exhaustion=True)))


def mkbuild(**kwargs):
  args = dict(
      id=1,
      project='chromium',
      bucket='luci.chromium.try',
      parameters={model.BUILDER_PARAMETER: 'linux-rel'},
      created_by=auth.Identity('user', 'john@example.com'),
  )
  args['parameters'].update(kwargs.pop('parameters', {}))
  args.update(kwargs)
  return model.Build(**args)
