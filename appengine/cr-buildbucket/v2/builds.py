# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides functions specific to v2 builds."""

import logging

from google.protobuf import timestamp_pb2

from proto import build_pb2
import bbutil
import buildtags
import config
import model

__all__ = [
    'MalformedBuild',
    'build_to_v2',
]

# TODO(crbug.com/917851): delete this file.


class MalformedBuild(Exception):
  """A build has unexpected format."""


def build_to_v2(build, build_steps=None):
  """Converts a model.Build to an incomplete build_pb2.Build.

  build_steps is model.BuildSteps. If provided, the the returned build includes
  steps.

  May raise MalformedBuild.
  """
  result_details = build.result_details or {}
  out_props = result_details.get('properties') or {}

  ret = build_pb2.Build(
      id=build.key.id(),
      builder=_get_builder_id(build),
      number=int(out_props.get('buildnumber') or 0),
      status=build.proto.status,
      created_by=build.created_by.to_bytes(),
      create_time=_dt2ts(build.create_time),
      start_time=_dt2ts(build.start_time),
      end_time=_dt2ts(build.complete_time),
      update_time=_dt2ts(build.update_time),
      cancel_reason=build.cancel_reason_v2,
      input=build_pb2.Build.Input(
          properties=build.input_properties,
          experimental=build.experimental,
          gitiles_commit=build.input_gitiles_commit,
      ),
      output=build_pb2.Build.Output(
          properties=bbutil.dict_to_struct(out_props)
      ),
      infra=build_pb2.BuildInfra(
          buildbucket=build_pb2.BuildInfra.Buildbucket(canary=build.canary),
          swarming=build_pb2.BuildInfra.Swarming(
              hostname=build.swarming_hostname,
              task_id=build.swarming_task_id,
              task_service_account=build.service_account,
          ),
          logdog=build_pb2.BuildInfra.LogDog(
              hostname=build.logdog_hostname,
              project=build.logdog_project,
              prefix=build.logdog_prefix,
          ),
          recipe=build.recipe,
      ),
  )
  if build.proto.HasField('infra_failure_reason'):
    ret.infra_failure_reason.CopyFrom(build.proto.infra_failure_reason)

  # TODO(nodir): delete task_result after 2018-06-01
  task_result = result_details.get('swarming', {}).get('task_result')
  if task_result:  # pragma: no cover
    for d in task_result.get('bot_dimensions', []):
      for v in d['value']:
        ret.infra.swarming.bot_dimensions.add(key=d['key'], value=v)
  else:
    bot_dimensions = (
        result_details.get('swarming', {}).get('bot_dimensions', {})
    )
    for k, values in sorted(bot_dimensions.iteritems()):
      for v in sorted(values):
        ret.infra.swarming.bot_dimensions.add(key=k, value=v)

  _parse_tags(ret, build.tags)

  if build_steps:
    ret.steps.extend(build_steps.step_container.steps)
  return ret


def _parse_tags(dest_msg, tags):
  saw_gitiles_commit = False

  for t in tags:
    # All builds in the datastore have tags that have a colon.
    k, v = buildtags.parse(t)
    if k == buildtags.BUILDER_KEY:
      # we've already parsed builder from parameters
      # and build creation code guarantees consinstency.
      # Exclude builder tag.
      continue
    if k == buildtags.BUILDSET_KEY:
      m = buildtags.RE_BUILDSET_GITILES_COMMIT.match(v)
      if m:
        if saw_gitiles_commit:
          raise MalformedBuild('more than one commits/gitiles/ buildset')
        saw_gitiles_commit = True
        if not dest_msg.input.HasField('gitiles_commit'):
          dest_msg.input.gitiles_commit.host = m.group(1)
          dest_msg.input.gitiles_commit.project = m.group(2)
          dest_msg.input.gitiles_commit.id = m.group(3)
        continue  # pragma: no cover | coverage bug

      m = buildtags.RE_BUILDSET_GERRIT_CL.match(v)
      if m:
        dest_msg.input.gerrit_changes.add(
            host=m.group(1),
            change=int(m.group(2)),
            patchset=int(m.group(3)),
        )
        # TODO(nodir): fetch project from gerrit
        continue
    elif k == buildtags.SWARMING_DIMENSION_KEY:
      if ':' in v:  # pragma: no branch
        k2, v2 = buildtags.parse(v)
        dest_msg.infra.swarming.task_dimensions.add(key=k2, value=v2)

      # This line is actually covered, but pycoverage thinks it is not.
      # It cannot be not covered because the if statement above is covered.
      continue  # pragma: no cover
    elif k == buildtags.SWARMING_TAG_KEY:
      if ':' in v:  # pragma: no branch
        k2, v2 = buildtags.parse(v)
        if k2 == 'priority':
          try:
            dest_msg.infra.swarming.priority = int(v2)
          except ValueError as ex:
            logging.warning('invalid tag %r: %s', t, ex)
        elif k2 == 'buildbucket_template_revision':  # pragma: no branch
          dest_msg.infra.buildbucket.service_config_revision = v2

      # Exclude all "swarming_tag" tags.
      continue
    elif k == buildtags.BUILD_ADDRESS_KEY:
      try:
        _, _, dest_msg.number = buildtags.parse_build_address(v)
        continue
      except ValueError as ex:  # pragma: no cover
        raise MalformedBuild('invalid build address "%s": %s' % (v, ex))
    elif k in ('swarming_hostname', 'swarming_task_id'):
      # These tags are added automatically and are covered by proto fields.
      # Omit them.
      continue

    dest_msg.tags.add(key=k, value=v)


def _get_builder_id(build):
  project_id, bucket_name = config.parse_bucket_id(build.bucket_id)
  return build_pb2.BuilderID(
      project=project_id,
      bucket=bucket_name,
      builder=(build.parameters or {}).get(model.BUILDER_PARAMETER) or '',
  )


def _dt2ts(dt):
  if dt is None:
    return None
  ts = timestamp_pb2.Timestamp()
  ts.FromDatetime(dt)
  return ts
