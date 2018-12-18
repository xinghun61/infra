# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from google.appengine.ext import ndb
from google.protobuf import json_format
from google.protobuf import struct_pb2
from protorpc import messages

from components import utils

import bbutil
import config
import logging
import model


def format_luci_bucket(bucket_id):
  """Returns V1 luci bucket name, e.g. "luci.chromium.try"."""
  return 'luci.%s.%s' % config.parse_bucket_id(bucket_id)


def parse_luci_bucket(bucket):
  """Converts V1 LUCI bucket to a bucket ID string.

  Returns '' if bucket is not a LUCI bucket.
  """
  parts = bucket.split('.', 2)
  if len(parts) == 3 and parts[0] == 'luci':
    return config.format_bucket_id(parts[1], parts[2])
  return ''


@ndb.tasklet
def to_bucket_id_async(bucket):
  """Converts a bucket string to a bucket id.

  A bucket string is either a bucket id (e.g. "chromium/try") or
  a legacy bucket name (e.g. "master.tryserver.x", "luci.chromium.try").

  Does not check access.

  Returns:
    bucket id string or None if such bucket does not exist.

  Raises:
    errors.InvalidInputError if bucket is invalid or ambiguous.
  """
  is_legacy = config.is_legacy_bucket_id(bucket)
  if not is_legacy:
    config.validate_bucket_id(bucket)
    raise ndb.Return(bucket)

  config.validate_bucket_name(bucket)

  bucket_id = parse_luci_bucket(bucket)
  if bucket_id:
    raise ndb.Return(bucket_id)

  # The slowest code path.
  # Does not apply to LUCI.
  bucket_id = config.resolve_bucket_name_async(bucket).get_result()
  if bucket_id:
    logging.info('resolved bucket id %r => %r', bucket, bucket_id)
  raise ndb.Return(bucket_id)


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
  service_account = messages.StringField(25)


def datetime_to_timestamp_safe(value):
  if value is None:
    return None
  return utils.datetime_to_timestamp(value)


def legacy_bucket_name(bucket_id, is_luci):
  if is_luci:
    # In V1, LUCI builds use a "long" bucket name, e.g. "luci.chromium.try"
    # as opposed to just "try". This is because in the past bucket names
    # were globally unique, as opposed to unique per project.
    return format_luci_bucket(bucket_id)

  _, bucket_name = config.parse_bucket_id(bucket_id)
  return bucket_name


# List of deprecated properties that are converted from float to int for
# backward compatibility.
# TODO(crbug.com/877161): remove this list.
INTEGER_PROPERTIES = [
    'buildnumber',
    'issue',
    'patchset',
    'patch_issue',
    'patch_set',
]


def properties_to_json(properties):
  """Converts properties to JSON.

  properties should be struct_pb2.Struct, but for convenience in tests
  a dict is also accepted.

  CAUTION: in general converts all numbers to floats,
  because JSON format does not distinguish floats and ints.
  For backward compatibility, temporarily (crbug.com/877161) renders widely
  used, deprecated properties as integers, see INTEGER_PROPERTIES.
  """
  assert isinstance(properties, (dict, struct_pb2.Struct)), properties
  if isinstance(properties, dict):  # pragma: no branch
    properties = bbutil.dict_to_struct(properties)

  # Note: this dict does not necessarily equal the original one.
  # In particular, an int may turn into a float.
  as_dict = json_format.MessageToDict(properties)

  for p in INTEGER_PROPERTIES:
    if isinstance(as_dict.get(p), float):
      as_dict[p] = int(as_dict[p])

  return json.dumps(as_dict, sort_keys=True)


def build_to_message(build, include_lease_key=False):
  """Converts model.Build to BuildMessage."""
  assert build
  assert build.key
  assert build.key.id()

  project_id, _ = config.parse_bucket_id(build.bucket_id)

  msg = BuildMessage(
      id=build.key.id(),
      project=project_id,
      bucket=legacy_bucket_name(build.bucket_id, build.is_luci),
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
      experimental=build.experimental,
      service_account=build.service_account,
      # when changing this function, make sure build_to_dict would still work
  )

  if build.lease_expiration_date is not None:
    msg.lease_expiration_ts = utils.datetime_to_timestamp(
        build.lease_expiration_date
    )
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
