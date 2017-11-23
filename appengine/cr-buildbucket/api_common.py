# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from protorpc import messages

from components import utils

import model


class BuildMessage(messages.Message):
  """Describes model.Build, see its docstring."""
  id = messages.IntegerField(1, required=True)
  bucket = messages.StringField(2, required=True)
  tags = messages.StringField(3, repeated=True)
  parameters_json = messages.StringField(4)
  status = messages.EnumField(model.BuildStatus, 5)
  result = messages.EnumField(model.BuildResult, 6)
  result_details_json = messages.StringField(7)
  failure_reason = messages.EnumField(model.FailureReason, 8)
  cancelation_reason = messages.EnumField(model.CancelationReason, 9)
  lease_expiration_ts = messages.IntegerField(10)
  lease_key = messages.IntegerField(11)
  url = messages.StringField(12)
  created_ts = messages.IntegerField(13)
  started_ts = messages.IntegerField(20)
  updated_ts = messages.IntegerField(14)
  completed_ts = messages.IntegerField(15)
  created_by = messages.StringField(16)
  status_changed_ts = messages.IntegerField(17)
  utcnow_ts = messages.IntegerField(18, required=True)
  retry_of = messages.IntegerField(19)
  canary_preference = messages.EnumField(model.CanaryPreference, 21)
  canary = messages.BooleanField(22)
  project = messages.StringField(23)
  experimental = messages.BooleanField(24)


def datetime_to_timestamp_safe(value):
  if value is None:
    return None
  return utils.datetime_to_timestamp(value)


def build_to_message(build, include_lease_key=False):
  """Converts model.Build to BuildMessage."""
  assert build
  assert build.key
  assert build.key.id()

  msg = BuildMessage(
      id=build.key.id(),
      bucket=build.bucket,
      tags=build.tags,
      parameters_json=json.dumps(build.parameters or {}, sort_keys=True),
      status=build.status,
      result=build.result,
      result_details_json=json.dumps(build.result_details),
      cancelation_reason=build.cancelation_reason,
      failure_reason=build.failure_reason,
      lease_key=build.lease_key if include_lease_key else None,
      url=build.url,
      created_ts=datetime_to_timestamp_safe(build.create_time),
      started_ts=datetime_to_timestamp_safe(build.start_time),
      updated_ts=datetime_to_timestamp_safe(build.update_time),
      completed_ts=datetime_to_timestamp_safe(build.complete_time),
      created_by=build.created_by.to_bytes() if build.created_by else None,
      status_changed_ts=datetime_to_timestamp_safe(build.status_changed_time),
      utcnow_ts=datetime_to_timestamp_safe(utils.utcnow()),
      retry_of=build.retry_of,
      canary_preference=build.canary_preference,
      canary=build.canary,
      project=build.project,
      experimental=build.experimental,
      # when changing this function, make sure build_to_dict would still work
  )
  if build.lease_expiration_date is not None:
    msg.lease_expiration_ts = utils.datetime_to_timestamp(
      build.lease_expiration_date)
  return msg


def build_to_dict(build, include_lease_key=False):
  """Converts a build to an externally consumable dict.

  This function returns a dict that a BuildMessage would be encoded to.
  """

  # Implementing this function in a generic way (message_to_dict) requires
  # knowledge of many protorpc and endpoints implementation details.
  # Not worth it.

  msg = build_to_message(build, include_lease_key=include_lease_key)

  # Special cases
  result = {
    'tags': msg.tags,  # a list
  }

  for f in msg.all_fields():
    v = msg.get_assigned_value(f.name)
    if f.name in result or v is None:
      # None is the default. It is omitted by Cloud Endpoints.
      continue
    if isinstance(v, messages.Enum):
      v = str(v)
    else:
      assert isinstance(v, (basestring, int, long, bool)), v
      if (isinstance(f, messages.IntegerField) and
          f.variant == messages.Variant.INT64):
        v = str(v)
    result[f.name] = v

  return result
