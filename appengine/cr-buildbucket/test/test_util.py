# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json

from google.protobuf import json_format
from google.protobuf import text_format

from google.appengine.ext import ndb
from google.protobuf import timestamp_pb2

from components import auth
from components import utils

from proto import build_pb2
from proto import common_pb2
from proto import project_config_pb2
import bbutil
import buildtags
import model


def ununicode(jsonish):  # pragma: no cover
  if isinstance(jsonish, dict):
    return {ununicode(k): ununicode(v) for k, v in jsonish.iteritems()}

  if isinstance(jsonish, list):
    return map(ununicode, jsonish)

  if isinstance(jsonish, unicode):
    return str(jsonish)

  return jsonish


def future(result):  # pragma: no cover
  f = ndb.Future()
  f.set_result(result)
  return f


def future_exception(ex):  # pragma: no cover
  f = ndb.Future()
  f.set_exception(ex)
  return f


def msg_to_dict(message):  # pragma: no cover
  """Converts a protobuf message to dict.

  Very inefficient. Use only in tests.
  Useful to compare protobuf messages, because unittest.assertEqual has special
  support for dicts, but not protobuf messages.
  """
  return json.loads(json_format.MessageToJson(message))


def parse_bucket_cfg(text):
  cfg = project_config_pb2.Bucket()
  text_format.Merge(text, cfg)
  return cfg


INDEXED_TAG = common_pb2.StringPair(key='buildset', value='1')
INDEXED_TAG_STRING = 'buildset:1'
BUILD_DEFAULTS = build_pb2.Build(
    builder=dict(project='chromium', bucket='try', builder='linux'),
    number=1,
    status=common_pb2.SCHEDULED,
    created_by='anonymous:anonymous',
    tags=[INDEXED_TAG],
    canary=False,
    exe=dict(
        cipd_package='infra/recipe_bundle',
        cipd_version='refs/heads/master',
    ),
    infra=dict(
        swarming=dict(
            hostname='swarming.example.com',
            task_id='deadbeef',
            task_service_account='service@example.com',
        ),
        logdog=dict(
            hostname='logdog.example.com',
            project='chromium',
            prefix='bb',
        ),
    )
)


def build(*args, **kwargs):  # pragma: no cover
  return build_bundle(*args, **kwargs).build


def build_bundle(for_creation=False, **build_proto_fields):  # pragma: no cover
  """Creates a model.BuildBundle from proto fields, with reasonable defaults.

  If for_creation is True, returned Build.proto.{infra, input.properties} will
  be set.
  """
  now = utils.utcnow()

  # Compute defaults.
  proto = copy.deepcopy(BUILD_DEFAULTS)
  if not proto.HasField('create_time'):
    proto.create_time.FromDatetime(now)
  proto.MergeFrom(build_pb2.Build(**build_proto_fields))
  proto.id = proto.id or model.create_build_ids(
      proto.create_time.ToDatetime(), 1, randomness=False
  )[0]

  with_start_time = (common_pb2.STARTED, common_pb2.SUCCESS)
  if not proto.HasField('start_time') and proto.status in with_start_time:
    proto.start_time.FromDatetime(now)
  completed = proto.status not in (common_pb2.SCHEDULED, common_pb2.STARTED)
  if not proto.HasField('end_time') and completed:
    proto.end_time.FromDatetime(now)
  proto.update_time.FromDatetime(now)

  if (proto.input.properties and
      not proto.infra.buildbucket.HasField('requested_properties')):
    proto.infra.buildbucket.requested_properties.CopyFrom(
        proto.input.properties
    )

  tags = {buildtags.unparse(t.key, t.value) for t in proto.tags}
  tags.add('builder:%s' % proto.builder.builder)
  if proto.number:
    tags.add(buildtags.build_address_tag(proto.builder, proto.number))
  proto.ClearField('tags')

  b = model.Build(
      id=proto.id,
      proto=proto,
      # TODO(crbug.com/970053): remove this in favor of
      # model.BuildInputProperties.
      input_properties_bytes=(
          proto.input.properties.SerializeToString() if not for_creation else ''
      ),
      created_by=auth.Identity.from_bytes(proto.created_by),
      create_time=proto.create_time.ToDatetime(),
      status_changed_time=now,
      tags=sorted(tags),
      parameters={},
      url='https://ci.example.com/%d' % proto.id,
      is_luci=True,
      swarming_task_key='swarming_task_key',
  )
  b.update_v1_status_fields()
  if proto.input.HasField('gitiles_commit'):
    b.parameters['changes'] = [{
        'author': {'email': 'bob@example.com'},
        'repo_url': 'https://chromium.googlesource.com/chromium/src',
    }]

  ret = model.BuildBundle(
      b,
      infra=model.BuildInfra(
          key=model.BuildInfra.key_for(b.key),
          infra=proto.infra.SerializeToString()
      ),
      input_properties=model.BuildInputProperties(
          key=model.BuildInputProperties.key_for(b.key),
          properties=proto.input.properties.SerializeToString(),
      ),
      output_properties=model.BuildOutputProperties(
          key=model.BuildOutputProperties.key_for(b.key),
          properties=proto.output.properties.SerializeToString(),
      ),
      steps=model.BuildSteps(
          key=model.BuildSteps.key_for(b.key),
          step_container_bytes=(
              build_pb2.Build(steps=proto.steps).SerializeToString()
          ),
      ),
  )

  if not for_creation:
    proto.ClearField('infra')
    proto.input.ClearField('properties')
  proto.output.ClearField('properties')
  proto.ClearField('steps')
  return ret


def dt2ts(dt):  # pragma: no cover
  if dt is None:
    return None
  ts = timestamp_pb2.Timestamp()
  ts.FromDatetime(dt)
  return ts
