# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import itertools
import random

from components import auth
from components import datastore_utils
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from google.protobuf import struct_pb2
from protorpc import messages

from proto import build_pb2
from proto import common_pb2
import buildtags
import config

BEGINING_OF_THE_WORLD = datetime.datetime(2010, 1, 1, 0, 0, 0, 0)
BUILD_TIMEOUT = datetime.timedelta(days=2)

# For how long to store builds.
BUILD_STORAGE_DURATION = datetime.timedelta(days=30 * 18)  # ~18mo

# If builds weren't scheduled for this duration on a given builder, the
# Builder entity is deleted.
BUILDER_EXPIRATION_DURATION = datetime.timedelta(weeks=4)

# Key in Build.parameters that specifies the builder name.
# TODO(nodir): remove, in favor of a new property in Build.
BUILDER_PARAMETER = 'builder_name'
PROPERTIES_PARAMETER = 'properties'  # TODO(nodir): move to api_common.py.


class BuildStatus(messages.Enum):
  # A build is created, can be leased by someone and started.
  SCHEDULED = 1
  # Someone has leased the build and marked it as started.
  STARTED = 2
  # A build is completed. See BuildResult for more details.
  COMPLETED = 3


class BuildResult(messages.Enum):
  # A build has completed successfully.
  SUCCESS = 1
  # A build has completed unsuccessfully.
  FAILURE = 2
  # A build was canceled.
  CANCELED = 3


class FailureReason(messages.Enum):
  # Build failed
  BUILD_FAILURE = 1
  # Something happened within buildbucket.
  BUILDBUCKET_FAILURE = 2
  # Something happened with build infrastructure, but not buildbucket.
  INFRA_FAILURE = 3
  # A build-system rejected a build because its definition is invalid.
  INVALID_BUILD_DEFINITION = 4


class CancelationReason(messages.Enum):
  # A build was canceled explicitly, probably by an API call.
  CANCELED_EXPLICITLY = 1
  # A build was canceled by buildbucket due to timeout.
  TIMEOUT = 2


class CanaryPreference(messages.Enum):
  # The build system will decide whether to use canary or not
  AUTO = 1
  # Use the production build infrastructure
  PROD = 2
  # Use the canary build infrastructure
  CANARY = 3


CANARY_PREFERENCE_TO_TRINARY = {
    CanaryPreference.AUTO: common_pb2.UNSET,
    CanaryPreference.PROD: common_pb2.NO,
    CanaryPreference.CANARY: common_pb2.YES,
}
TRINARY_TO_CANARY_PREFERENCE = {
    v: k for k, v in CANARY_PREFERENCE_TO_TRINARY.iteritems()
}


class PubSubCallback(ndb.Model):
  """Parameters for a callack push task."""
  topic = ndb.StringProperty(required=True, indexed=False)
  auth_token = ndb.StringProperty(indexed=False)
  user_data = ndb.StringProperty(indexed=False)


class BucketState(ndb.Model):
  """Persistent state of a single bucket."""
  # If True, no new builds may be leased for this bucket.
  is_paused = ndb.BooleanProperty()


def is_terminal_status(status):  # pragma: no cover
  return status not in (
      common_pb2.STATUS_UNSPECIFIED, common_pb2.SCHEDULED, common_pb2.STARTED
  )


class Build(ndb.Model):
  """Describes a build.

  Build key:
    Build keys are autogenerated, monotonically decreasing integers.
    That is, when sorted by key, new builds are first.
    Build has no parent.

    Build id is a 64 bits integer represented as a string to the user.
    - 1 highest order bit is set to 0 to keep value positive.
    - 43 bits are 43 lower bits of bitwise-inverted time since
      BEGINING_OF_THE_WORLD at 1ms resolution.
      It is good for 2**43 / 365.3 / 24 / 60 / 60 / 1000 = 278 years
      or 2010 + 278 = year 2288.
    - 16 bits are set to a random value. Assuming an instance is internally
      consistent with itself, it can ensure to not reuse the same 16 bits in two
      consecutive requests and/or throttle itself to one request per
      millisecond. Using random value reduces to 2**-15 the probability of
      collision on exact same timestamp at 1ms resolution, so a maximum
      theoretical rate of 65536000 requests/sec but an effective rate in the
      range of ~64k qps without much transaction conflicts. We should be fine.
    - 4 bits are 0. This is to represent the 'version' of the entity
      schema.

    The idea is taken from Swarming TaskRequest entity:
    https://code.google.com/p/swarming/source/browse/appengine/swarming/server/task_request.py#329
  """

  # ndb library sometimes silently ignores memcache errors
  # => memcache is not synchronized with datastore
  # => a build never finishes from the app code perspective
  # => builder is stuck for days.
  # We workaround this problem by setting a timeout.
  _memcache_timeout = 600  # 10m

  # Stores the build proto. The primary property of this entity.
  # Majority of the other properties are either derivatives of this field or
  # legacy.
  #
  # Does not include:
  #   output.properties: see BuildOutputProperties
  #   steps: see BuildSteps.
  #
  # Transition period: proto is either None or complete, i.e. created by
  # creation.py or fix_builds.py.
  proto = datastore_utils.ProtobufProperty(build_pb2.Build)

  # Specifies whether canary of build infrastructure should be used for this
  # build.
  canary_preference = msgprop.EnumProperty(CanaryPreference, indexed=False)

  # == proto-derived properties ================================================
  #
  # These properties are derived from "proto" properties.
  # They are used to index builds.
  # TODO(crbug.com/917851): make them computed.

  status_v2 = ndb.ComputedProperty(lambda self: self.proto.status)

  @property
  def is_ended(self):  # pragma: no cover
    return is_terminal_status(self.proto.status)

  incomplete = ndb.ComputedProperty(lambda self: not self.is_ended)

  # A container of builds, defines a security domain.
  # Format: "<project_id>/<bucket_name>".
  # "luci.<project_id>." prefix is stripped from bucket name,
  # e.g. "chromium/try", not "chromium/luci.chromium.try".
  bucket_id = ndb.StringProperty()

  # ID of the LUCI project to which this build belongs.
  project = ndb.ComputedProperty(
      lambda self: config.parse_bucket_id(self.bucket_id)[0]
  )

  # Superset of proto.tags. May contain auto-added tags.
  # A list of colon-separated key-value pairs.
  tags = ndb.StringProperty(repeated=True)

  # If True, the build won't affect monitoring and won't be surfaced in
  # search results unless explicitly requested.
  experimental = ndb.BooleanProperty()

  swarming_task_id = ndb.StringProperty()

  @property
  def is_luci(self):  # pragma: no cover
    return bool(self.swarming_hostname)

  @property
  def is_ended(self):  # pragma: no cover
    return self.proto.status not in (
        common_pb2.STATUS_UNSPECIFIED, common_pb2.SCHEDULED, common_pb2.STARTED
    )

  # == Legacy properties =======================================================

  status_legacy = msgprop.EnumProperty(
      BuildStatus, default=BuildStatus.SCHEDULED, name='status'
  )

  status_changed_time = ndb.DateTimeProperty(auto_now_add=True)

  # immutable arbitrary build parameters.
  parameters = datastore_utils.DeterministicJsonProperty(json_type=dict)

  # PubSub message parameters for build status change notifications.
  # TODO(nodir): replace with notification_pb2.NotificationConfig.
  pubsub_callback = ndb.StructuredProperty(PubSubCallback, indexed=False)

  # id of the original build that this build was derived from.
  retry_of = ndb.IntegerProperty()

  # a URL to a build-system-specific build, viewable by a human.
  url = ndb.StringProperty(indexed=False)

  # V1 status properties. Computed by _pre_put_hook.
  result = msgprop.EnumProperty(BuildResult)
  result_details = datastore_utils.DeterministicJsonProperty(json_type=dict)
  cancelation_reason = msgprop.EnumProperty(CancelationReason)
  failure_reason = msgprop.EnumProperty(FailureReason)

  # Lease-time properties.

  # TODO(nodir): move lease to a separate entity under Build.
  # It would be more efficient.
  # current lease expiration date.
  # The moment the build is leased, |lease_expiration_date| is set to
  # (utcnow + lease_duration).
  lease_expiration_date = ndb.DateTimeProperty()
  # None if build is not leased, otherwise a random value.
  # Changes every time a build is leased. Can be used to verify that a client
  # is the leaseholder.
  lease_key = ndb.IntegerProperty(indexed=False)
  # True if the build is currently leased. Otherwise False
  is_leased = ndb.ComputedProperty(lambda self: self.lease_key is not None)
  leasee = auth.IdentityProperty()
  never_leased = ndb.BooleanProperty()

  # == Properties redundant with "proto" =======================================
  #
  # TODO(crbug.com/917851): delete these properties or move to "derived".

  update_time = ndb.DateTimeProperty(auto_now=True)
  create_time = ndb.DateTimeProperty(auto_now_add=True)
  created_by = auth.IdentityProperty()
  input_gitiles_commit = datastore_utils.ProtobufProperty(
      common_pb2.GitilesCommit
  )

  # when the build started. Unknown for old builds.
  start_time = ndb.DateTimeProperty()

  # True if canary build infrastructure is used to run this build.
  # It may be None only in SCHEDULED state. Otherwise it must be True or False.
  # If canary_preference is CANARY, this field value does not have to be True,
  # e.g. if the build infrastructure does not have a canary.
  canary = ndb.BooleanProperty()

  complete_time = ndb.DateTimeProperty()
  cancel_reason_v2 = datastore_utils.ProtobufProperty(build_pb2.CancelReason)

  swarming_hostname = ndb.StringProperty()
  service_account = ndb.StringProperty()

  # LogDog integration

  logdog_hostname = ndb.StringProperty()
  logdog_project = ndb.StringProperty()
  logdog_prefix = ndb.StringProperty()

  recipe = datastore_utils.ProtobufProperty(build_pb2.BuildInfra.Recipe)

  def _pre_put_hook(self):
    """Checks Build invariants before putting."""
    super(Build, self)._pre_put_hook()
    config.validate_bucket_id(self.bucket_id)
    is_started = self.proto.status == common_pb2.STARTED
    is_ended = self.is_ended
    is_leased = self.lease_key is not None
    assert not (is_ended and is_leased)
    assert (self.lease_expiration_date is not None) == is_leased
    assert (self.leasee is not None) == is_leased
    # no cover due to a bug in coverage (https://stackoverflow.com/a/35325514)

    tag_delm = buildtags.DELIMITER
    assert (not self.tags or
            all(tag_delm in t for t in self.tags))  # pragma: no cover
    assert self.create_time
    assert (self.complete_time is not None) == is_ended
    assert not is_started or self.start_time
    assert not self.start_time or self.start_time >= self.create_time
    assert not self.complete_time or self.complete_time >= self.create_time
    assert (
        not self.complete_time or not self.start_time or
        self.complete_time >= self.start_time
    )

    self.experimental = bool(self.experimental)
    self.tags = sorted(set(self.tags))

    self.update_v1_status_fields()
    if self.proto:  # pragma: no branch
      # TODO(crbug.com/917851): once all entities have proto property,
      # update proto fields directly and remove this code.
      # This code updates only fields that are changed after creation.
      # Fields immutable after creation must be set already.
      self.proto.update_time.FromDatetime(self.update_time)
      if self.start_time:  # pragma: no branch
        self.proto.start_time.FromDatetime(self.start_time)
      if self.complete_time:  # pragma: no branch
        self.proto.end_time.FromDatetime(self.complete_time)

  def update_v1_status_fields(self):
    """Updates V1 status fields."""
    self.status_legacy = None
    self.result = None
    self.failure_reason = None
    self.cancelation_reason = None

    status_v2 = self.proto.status
    if status_v2 == common_pb2.SCHEDULED:
      self.status_legacy = BuildStatus.SCHEDULED
    elif status_v2 == common_pb2.STARTED:
      self.status_legacy = BuildStatus.STARTED
    elif status_v2 == common_pb2.SUCCESS:
      self.status_legacy = BuildStatus.COMPLETED
      self.result = BuildResult.SUCCESS
    elif status_v2 == common_pb2.FAILURE:
      self.status_legacy = BuildStatus.COMPLETED
      self.result = BuildResult.FAILURE
      self.failure_reason = FailureReason.BUILD_FAILURE
    elif status_v2 == common_pb2.INFRA_FAILURE:
      self.status_legacy = BuildStatus.COMPLETED
      if self.proto.infra_failure_reason.resource_exhaustion:
        # In python implementation, V2 resource exhaustion is V1 timeout.
        self.result = BuildResult.CANCELED
        self.cancelation_reason = CancelationReason.TIMEOUT
      else:
        self.result = BuildResult.FAILURE
        self.failure_reason = FailureReason.INFRA_FAILURE
    elif status_v2 == common_pb2.CANCELED:
      self.status_legacy = BuildStatus.COMPLETED
      self.result = BuildResult.CANCELED
      self.cancelation_reason = CancelationReason.CANCELED_EXPLICITLY
    else:  # pragma: no cover
      assert False, status_v2

  def regenerate_lease_key(self):
    """Changes lease key to a different random int."""
    while True:
      new_key = random.randint(0, 1 << 31)
      if new_key != self.lease_key:  # pragma: no branch
        self.lease_key = new_key
        break

  def clear_lease(self):  # pragma: no cover
    """Clears build's lease attributes."""
    self.lease_key = None
    self.lease_expiration_date = None
    self.leasee = None


class BuildDetailEntity(ndb.Model):
  """A base class for a Datastore entity that stores some details of one Build.

  Entity key: Parent is Build entity key. ID is 1.
  """

  @classmethod
  def key_for(cls, build_key):  # pragma: no cover
    return ndb.Key(cls, 1, parent=build_key)


class BuildOutputProperties(BuildDetailEntity):
  """Stores buildbucket.v2.Build.output.properties."""
  properties = datastore_utils.ProtobufProperty(struct_pb2.Struct)


class BuildSteps(BuildDetailEntity):
  """Stores buildbucket.v2.Build.steps."""

  # max length of steps attribute, uncompressed.
  MAX_STEPS_LEN = 1024 * 1024

  # buildbucket.v2.Build binary protobuf message with only "steps" field set.
  step_container = datastore_utils.ProtobufProperty(
      build_pb2.Build,
      name='steps',
      max_length=MAX_STEPS_LEN,
      compressed=True,
  )

  def _pre_put_hook(self):
    """Checks BuildSteps invariants before putting."""
    super(BuildSteps, self)._pre_put_hook()
    assert self.step_container is not None


# Tuple of classes representing entity kinds that living under Build entity.
# Such entities must be deleted if Build entity is deleted.
BUILD_CHILD_CLASSES = (
    BuildOutputProperties,
    BuildSteps,
)


class Builder(ndb.Model):
  """A builder in a bucket.

  Used internally for metrics.
  Registered automatically by scheduling a build.
  Unregistered automatically by not scheduling builds for
  BUILDER_EXPIRATION_DURATION.

  Entity key:
    No parent. ID is a string with format "{project}:{bucket}:{builder}".
  """

  # Last time we received a valid build scheduling request for this builder.
  # Probabilistically updated by services.py, see its _should_update_builder.
  last_scheduled = ndb.DateTimeProperty()


_TIME_RESOLUTION = datetime.timedelta(milliseconds=1)
_BUILD_ID_SUFFIX_LEN = 20
# Size of a build id segment covering one millisecond.
ONE_MS_BUILD_ID_RANGE = 1 << _BUILD_ID_SUFFIX_LEN


def _id_time_segment(dtime):
  assert dtime
  assert dtime >= BEGINING_OF_THE_WORLD
  delta = dtime - BEGINING_OF_THE_WORLD
  now = int(delta.total_seconds() * 1000.)
  return (~now & ((1 << 43) - 1)) << 20


def create_build_ids(dtime, count, randomness=True):
  """Returns a range of valid build ids, as integers and based on a datetime.

  See Build's docstring, "Build key" section.
  """
  # Build ID bits: "0N{43}R{16}V{4}"
  # where N is now bits, R is random bits and V is version bits.
  build_id = int(_id_time_segment(dtime))
  build_id = build_id | ((random.getrandbits(16) << 4) if randomness else 0)
  return [build_id - i * (1 << 4) for i in xrange(count)]


def build_id_range(create_time_low, create_time_high):
  """Converts a creation time range to build id range.

  Low/high bounds are inclusive/exclusive respectively, for both time and id
  ranges.
  """
  id_low = None
  id_high = None
  if create_time_low is not None:  # pragma: no branch
    # convert inclusive to exclusive
    id_high = _id_time_segment(create_time_low - _TIME_RESOLUTION)
  if create_time_high is not None:  # pragma: no branch
    # convert exclusive to inclusive
    id_low = _id_time_segment(create_time_high - _TIME_RESOLUTION)
  return id_low, id_high


@ndb.tasklet
def builds_to_protos_async(
    builds, load_steps=False, load_output_properties=False
):
  """Converts Build objects to build_pb2.Build messages.

  Mutates builds' "proto" field values and returns them.
  """
  if load_steps:
    steps_futs = [BuildSteps.key_for(b.key).get_async() for b in builds]
  else:
    steps_futs = itertools.repeat(None)

  if load_output_properties:
    out_props_futs = [
        BuildOutputProperties.key_for(b.key).get_async() for b in builds
    ]
  else:
    out_props_futs = itertools.repeat(None)

  for b, steps_fut, out_props_fut in zip(builds, steps_futs, out_props_futs):
    # Old builds do not have proto.id
    b.proto.id = b.key.id()

    if steps_fut:
      steps = yield steps_fut
      if steps:  # pragma: no branch
        b.proto.steps.extend(steps.step_container.steps)

    if out_props_fut:
      out_props = yield out_props_fut
      if out_props:  # pragma: no branch
        b.proto.output.properties.CopyFrom(out_props.properties)

  raise ndb.Return([b.proto for b in builds])
