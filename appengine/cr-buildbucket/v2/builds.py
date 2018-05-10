# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides functions specific to v2 builds."""

import logging

from google.protobuf import struct_pb2
from google.protobuf import timestamp_pb2

from . import errors
from proto import build_pb2
from proto import common_pb2
import model
import swarming

BUILDER_PARAMETER = 'builder_name'


def build_to_v2_partial(build):
  """Converts a model.Build to an incomplete build_pb2.Build.

  The returned build does not include steps.

  May raise errors.UnsupportedBuild or errors.MalformedBuild.
  """
  result_details = build.result_details or {}
  ret = build_pb2.Build(
      id=build.key.id(),
      builder=_get_builder_id(build),
      number=result_details.get('properties', {}).get('buildnumber') or 0,
      created_by=build.created_by.to_bytes(),
      view_url=build.url,
      create_time=_dt2ts(build.create_time),
      start_time=_dt2ts(build.start_time),
      end_time=_dt2ts(build.complete_time),
      update_time=_dt2ts(build.update_time),
      status=_get_status(build),
      input=build_pb2.Build.Input(
          properties=_dict_to_struct(build.parameters.get('properties')),
          experimental=build.experimental,
      ),
      output=build_pb2.Build.Output(
          properties=_dict_to_struct(result_details.get('properties')),),
      infra=build_pb2.BuildInfra(
          buildbucket=build_pb2.BuildInfra.Buildbucket(canary=build.canary),
          swarming=build_pb2.BuildInfra.Swarming(
              hostname=build.swarming_hostname,
              task_id=build.swarming_task_id,
              task_service_account=build.service_account,
          ),
      ),
  )

  task_result = result_details.get('swarming', {}).get('task_result', {})
  for d in task_result.get('bot_dimensions', []):
    for v in d['value']:
      ret.infra.swarming.bot_dimensions.add(key=d['key'], value=v)

  _parse_tags(ret, build.tags)
  return ret


def _parse_tags(dest_msg, tags):
  for t in tags:
    # All builds in the datastore have tags that have a colon.
    k, v = t.split(':', 1)
    if k == 'builder':
      # we've already parsed builder from parameters
      # and build creation code guarantees consinstency.
      # Exclude builder tag.
      continue
    if k == 'buildset':
      m = model.RE_BUILDSET_GITILES_COMMIT.match(v)
      if m:
        dest_msg.input.gitiles_commits.add(
            host=m.group(1),
            project=m.group(2),
            id=m.group(3),
        )
        continue

      m = model.RE_BUILDSET_GERRIT_CL.match(v)
      if m:
        dest_msg.input.gerrit_changes.add(
            host=m.group(1),
            change=int(m.group(2)),
            patchset=int(m.group(3)),
        )
        # TODO(nodir): fetch project from gerrit
        continue
    elif k == 'swarming_dimension':
      if ':' in v:  # pragma: no branch
        k2, v2 = v.split(':', 1)
        dest_msg.infra.swarming.task_dimensions.add(key=k2, value=v2)

      # This line is actually covered, but pycoverage thinks it is not.
      # It cannot be not covered because the if statement above is covered.
      continue  # pragma: no cover
    elif k == 'swarming_tag':
      if ':' in v:  # pragma: no branch
        k2, v2 = v.split(':', 1)
        if k2 == 'priority':
          try:
            dest_msg.infra.swarming.priority = int(v2)
          except ValueError as ex:
            logging.warning('invalid tag %r: %s', t, ex)
        elif k2 == 'buildbucket_template_revision':  # pragma: no branch
          dest_msg.infra.buildbucket.service_config_revision = v2

      # Exclude all "swarming_tag" tags.
      continue
    elif k == swarming.BUILD_ADDRESS_TAG_KEY:
      try:
        _, _, dest_msg.number = swarming.parse_build_address(v)
        continue
      except ValueError as ex:  # pragma: no cover
        raise errors.MalformedBuild('invalid build address "%s": %s' % (v, ex))
    elif k in ('swarming_hostname', 'swarming_task_id'):
      # These tags are added automatically and are covered by proto fields.
      # Omit them.
      continue

    dest_msg.tags.add(key=k, value=v)


def _get_builder_id(build):
  builder = (build.parameters or {}).get(BUILDER_PARAMETER)
  if not builder:
    raise errors.UnsupportedBuild(
        'does not have %s parameter' % BUILDER_PARAMETER)

  bucket = build.bucket
  # in V2, we drop "luci.{project}." prefix.
  luci_prefix = 'luci.%s.' % build.project
  if bucket.startswith(luci_prefix):
    bucket = bucket[len(luci_prefix):]
  return build_pb2.Builder.ID(
      project=build.project,
      bucket=bucket,
      builder=builder,
  )


def _get_status(build):
  if build.status == model.BuildStatus.SCHEDULED:
    return common_pb2.SCHEDULED
  elif build.status == model.BuildStatus.STARTED:
    return common_pb2.STARTED
  elif build.status == model.BuildStatus.COMPLETED:  # pragma: no branch
    if build.result == model.BuildResult.SUCCESS:
      return common_pb2.SUCCESS
    elif build.result == model.BuildResult.FAILURE:
      if build.failure_reason == model.FailureReason.BUILD_FAILURE:
        return common_pb2.FAILURE
      else:
        return common_pb2.INFRA_FAILURE
    elif build.result == model.BuildResult.CANCELED:  # pragma: no branch
      reason = build.cancelation_reason
      if reason == model.CancelationReason.CANCELED_EXPLICITLY:
        return common_pb2.CANCELED
      else:
        return common_pb2.INFRA_FAILURE

  raise errors.MalformedBuild(  # pragma: no cover
      'invalid status in build %d' % build.key.id())


def _dict_to_struct(d):
  if d is None:
    return None
  s = struct_pb2.Struct()
  s.update(d)
  return s


def _dt2ts(dt):
  if dt is None:
    return None
  ts = timestamp_pb2.Timestamp()
  ts.FromDatetime(dt)
  return ts
