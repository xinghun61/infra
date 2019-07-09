# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import urlparse

from google.appengine.api import taskqueue
from google.appengine.api import modules
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.protobuf import struct_pb2

from components import auth
from components import utils
import gae_ts_mon

from proto import common_pb2
import buildtags
import config
import errors
import events
import model
import search
import swarming
import user

MAX_RETURN_BUILDS = 100
DEFAULT_LEASE_DURATION = datetime.timedelta(minutes=1)

# A cumlative counter of access denied errors in peek() method.
# This metric exists because defining it on the buildbucket server is easier
# than modifying Buildbot. It is very specific intentionally.
PEEK_ACCESS_DENIED_ERROR_COUNTER = gae_ts_mon.CounterMetric(
    'buildbucket/peek_access_denied_errors', 'Number of errors in peek API',
    [gae_ts_mon.StringField('bucket')]
)


def validate_lease_key(lease_key):
  if lease_key is None:
    raise errors.InvalidInputError('Lease key is not provided')


def validate_url(url):
  if url is None:
    return
  if not isinstance(url, basestring):
    raise errors.InvalidInputError('url must be string')
  parsed = urlparse.urlparse(url)
  if not parsed.netloc:
    raise errors.InvalidInputError('url must be absolute')
  if parsed.scheme.lower() not in ('http', 'https'):
    raise errors.InvalidInputError(
        'Unexpected url scheme: "%s"' % parsed.scheme
    )


def unregister_builders():
  """Unregisters builders that didn't have builds for 4 weeks."""
  threshold = utils.utcnow() - model.BUILDER_EXPIRATION_DURATION
  q = model.Builder.query(model.Builder.last_scheduled < threshold)
  keys = q.fetch(keys_only=True)
  if keys:  # pragma: no branch
    logging.warning('unregistered builders: %s', [k.id() for k in keys])
    ndb.delete_multi(keys)


@ndb.tasklet
def get_async(build_id):
  """Gets a build by |build_id|.

  Requires the current user to have permissions to view the build.
  """
  build = yield model.Build.get_by_id_async(build_id)
  if not build:
    raise ndb.Return(None)
  if not (yield user.can_view_build_async(build)):
    raise user.current_identity_cannot('view build %s', build.key.id())
  raise ndb.Return(build)


def peek(bucket_ids, max_builds=None, start_cursor=None):
  """Returns builds available for leasing in the specified |bucket_ids|.

  Builds are sorted by creation time, oldest first.

  Args:
    bucket_ids (list of string): fetch only builds in any of |bucket_ids|.
    max_builds (int): maximum number of builds to return. Defaults to 10.
    start_cursor (string): a value of "next" cursor returned by previous
      peek call. If not None, return next builds in the query.

  Returns:
    A tuple:
      builds (list of Builds): available builds.
      next_cursor (str): cursor for the next page.
        None if there are no more builds.
  """
  if not bucket_ids:
    raise errors.InvalidInputError('No buckets specified')
  bucket_ids = sorted(set(bucket_ids))
  search.check_acls_async(
      bucket_ids, inc_metric=PEEK_ACCESS_DENIED_ERROR_COUNTER
  ).get_result()
  for bid in bucket_ids:
    _reject_swarming_bucket(bid)
  max_builds = search.fix_max_builds(max_builds)

  # Prune any buckets that are paused.
  bucket_states = _get_bucket_states(bucket_ids)
  active_buckets = []
  for b in bucket_ids:
    if bucket_states[b].is_paused:
      logging.warning('Ignoring paused bucket: %s.', b)
      continue
    active_buckets.append(b)

  # Short-circuit: if there are no remaining buckets to query, then we're done.
  if not active_buckets:
    return ([], None)

  q = model.Build.query(
      model.Build.status_legacy == model.BuildStatus.SCHEDULED,
      model.Build.is_leased == False,
      model.Build.bucket_id.IN(active_buckets),
  )
  q = q.order(-model.Build.key)  # oldest first.

  # Check once again locally because an ndb query may return an entity not
  # satisfying the query.
  def local_predicate(b):
    return (
        b.status_legacy == model.BuildStatus.SCHEDULED and not b.is_leased and
        b.bucket_id in active_buckets
    )

  return search.fetch_page_async(
      q, max_builds, start_cursor, predicate=local_predicate
  ).get_result()


def _get_leasable_build(build_id):
  build = model.Build.get_by_id(build_id)
  if build is None:
    raise errors.BuildNotFoundError()
  if not user.can_lease_build_async(build).get_result():
    raise user.current_identity_cannot('lease build %s', build.key.id())
  if build.is_luci:
    raise errors.InvalidInputError('cannot lease a swarmbucket build')
  return build


def lease(build_id, lease_expiration_date=None):
  """Leases the build, makes it unavailable for the leasing.

  Changes lease_key to a different value.

  After the lease expires, a cron task will make the build leasable again.

  Args:
    build_id (int): build id.
    lease_expiration_date (datetime.datetime): lease expiration date.
      Defaults to 10 seconds from now.

  Returns:
    Tuple:
      success (bool): True if the build was leased
      build (ndb.Build)
  """
  errors.validate_lease_expiration_date(lease_expiration_date)
  if lease_expiration_date is None:
    lease_expiration_date = utils.utcnow() + DEFAULT_LEASE_DURATION

  @ndb.transactional
  def try_lease():
    build = _get_leasable_build(build_id)

    if build.proto.status != common_pb2.SCHEDULED or build.is_leased:
      return False, build

    build.lease_expiration_date = lease_expiration_date
    build.regenerate_lease_key()
    build.leasee = auth.get_current_identity()
    build.never_leased = False
    build.put()
    return True, build

  updated, build = try_lease()
  if updated:
    events.on_build_leased(build)
  return updated, build


def _check_lease(build, lease_key):
  if lease_key != build.lease_key:
    raise errors.LeaseExpiredError(
        'lease_key for build %s is incorrect. Your lease might be expired.' %
        build.key.id()
    )


def reset(build_id):
  """Forcibly unleases the build and resets its state.

  Resets status, url and lease_key.

  Returns:
    The reset Build.
  """

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)
    if not user.can_reset_build_async(build).get_result():
      raise user.current_identity_cannot('reset build %s', build.key.id())
    if build.is_ended:
      raise errors.BuildIsCompletedError('Cannot reset a completed build')
    build.proto.status = common_pb2.SCHEDULED
    build.status_changed_time = utils.utcnow()
    build.clear_lease()
    build.url = None
    _fut_results(build.put_async(), events.on_build_resetting_async(build))
    return build

  build = txn()
  events.on_build_reset(build)
  return build


def start(build_id, lease_key, url):
  """Marks build as STARTED. Idempotent.

  Args:
    build_id: id of the started build.
    lease_key: current lease key.
    url (str): a URL to a build-system-specific build, viewable by a human.

  Returns:
    The updated Build.
  """
  validate_lease_key(lease_key)
  validate_url(url)

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.proto.status == common_pb2.STARTED:
      if build.url == url:
        return False, build
      build.url = url
      build.put()
      return True, build

    if build.is_ended:
      raise errors.BuildIsCompletedError('Cannot start a completed build')

    assert build.proto.status == common_pb2.SCHEDULED

    _check_lease(build, lease_key)

    now = utils.utcnow()
    build.proto.start_time.FromDatetime(now)
    build.proto.status = common_pb2.STARTED
    build.status_changed_time = now
    build.url = url
    _fut_results(build.put_async(), events.on_build_starting_async(build))
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_started(build)
  return build


def _get_bucket_states(bucket_ids):
  """Returns the list of bucket states for all named buckets.

  Args:
    bucket_ids (list): A list of bucket id strings.
      Assumed to have already been validated.

  Returns (dict):
    A map of bucket id to BucketState for that bucket.
  """
  # Get bucket keys and deduplicate.
  default_states = [model.BucketState(id=b) for b in bucket_ids]
  states = ndb.get_multi(state.key for state in default_states)
  for i, state in enumerate(states):
    if not state:
      states[i] = default_states[i]
  return dict(zip(bucket_ids, states))


@ndb.tasklet
def heartbeat_async(build_id, lease_key, lease_expiration_date):
  """Extends build lease.

  Args:
    build_id: id of the build.
    lease_key: current lease key.
    lease_expiration_date (datetime.timedelta): new lease expiration date.

  Returns:
    The updated Build as Future.
  """

  @ndb.transactional_tasklet
  def txn():
    validate_lease_key(lease_key)
    if lease_expiration_date is None:
      raise errors.InvalidInputError('Lease expiration date not specified')
    errors.validate_lease_expiration_date(lease_expiration_date)
    build = yield model.Build.get_by_id_async(build_id)
    if build is None:
      raise errors.BuildNotFoundError()
    if build.is_ended:
      msg = ''
      if (build.result == model.BuildResult.CANCELED and
          build.cancelation_reason == model.CancelationReason.TIMEOUT):
        msg = (
            'Build was marked as timed out '
            'because it did not complete for %s' % model.BUILD_TIMEOUT
        )
      raise errors.BuildIsCompletedError(msg)
    _check_lease(build, lease_key)
    build.lease_expiration_date = lease_expiration_date
    yield build.put_async()
    raise ndb.Return(build)

  try:
    build = yield txn()
  except Exception as ex:
    events.on_heartbeat_failure(build_id, ex)
    raise
  raise ndb.Return(build)


def heartbeat(build_id, lease_key, lease_expiration_date):
  future = heartbeat_async(build_id, lease_key, lease_expiration_date)
  return future.get_result()


def heartbeat_batch(heartbeats):
  """Extends build leases in a batch.

  Args:
    heartbeats (list of dict): list of builds to update. Each dict is kwargs
    for heartbeat() method.

  Returns:
    List of (build_id, build, exception) tuples.
  """
  build_ids = [h['build_id'] for h in heartbeats]
  logging.info('Batch heartbeat: %s', build_ids)
  futures = [(h, heartbeat_async(**h)) for h in heartbeats]

  def get_result(hb, future):
    build_id = hb['build_id']
    exc = future.get_exception()
    if not exc:
      return build_id, future.get_result(), None
    else:
      return build_id, None, exc

  return [get_result(h, f) for h, f in futures]


@ndb.tasklet
def _put_output_properties_async(build_key, legacy_result_details):
  prop_dict = (legacy_result_details or {}).get('properties')
  if isinstance(prop_dict, dict):
    props = struct_pb2.Struct()
    props.update(prop_dict)
    yield model.BuildOutputProperties(
        key=model.BuildOutputProperties.key_for(build_key),
        properties=props.SerializeToString(),
    ).put_async()


def _complete(
    build_id, lease_key, status, result_details, url=None, new_tags=None
):
  """Marks a build as completed. Used by succeed and fail methods."""
  validate_lease_key(lease_key)
  validate_url(url)
  buildtags.validate_tags(new_tags, 'append')
  assert model.is_terminal_status(status), status

  @ndb.transactional
  def txn():
    build = _get_leasable_build(build_id)

    if build.is_ended:
      if (build.proto.status == status and
          build.result_details == result_details and build.url == url):
        return False, build
      raise errors.BuildIsCompletedError(
          'Build %s has already completed' % build_id
      )
    _check_lease(build, lease_key)

    now = utils.utcnow()
    build.proto.status = status
    build.status_changed_time = now
    build.proto.end_time.FromDatetime(now)
    if url is not None:  # pragma: no branch
      build.url = url
    build.result_details = result_details
    if new_tags:
      build.tags.extend(new_tags)
      build.tags = sorted(set(build.tags))
    build.clear_lease()

    _fut_results(
        build.put_async(),
        events.on_build_completing_async(build),
        _put_output_properties_async(build.key, result_details),
    )
    return True, build

  updated, build = txn()
  if updated:
    events.on_build_completed(build)
  return build


def succeed(build_id, lease_key, result_details=None, url=None, new_tags=None):
  """Marks a build as succeeded. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    result_details (dict): build result description.
    new_tags (list of str): list of new tags to add to the Build.

  Returns:
    The succeeded Build.
  """
  return _complete(
      build_id,
      lease_key,
      common_pb2.SUCCESS,
      result_details,
      url=url,
      new_tags=new_tags
  )


def fail(
    build_id,
    lease_key,
    result_details=None,
    failure_reason=None,
    url=None,
    new_tags=None
):
  """Marks a build as failed. Idempotent.

  Args:
    build_id: id of the build to complete.
    lease_key: current lease key.
    failure_reason (model.FailureReason): why the build failed.
      Defaults to model.FailureReason.BUILD_FAILURE.
    result_details (dict): build result description.
    new_tags (list of str): list of new tags to add to the Build.

  Returns:
    The failed Build.
  """
  if not failure_reason or failure_reason == model.FailureReason.BUILD_FAILURE:
    status = common_pb2.FAILURE
  else:
    status = common_pb2.INFRA_FAILURE
  return _complete(
      build_id,
      lease_key,
      status,
      result_details,
      url=url,
      new_tags=new_tags,
  )


@ndb.tasklet
def cancel_async(build_id, summary_markdown='', result_details=None):
  """Cancels build. Does not require a lease key.

  The current user has to have a permission to cancel a build in the
  bucket.

  Args:
    build_id: id of the build to cancel.
    summary_markdown (basestring): human-readable explanation.
    result_details (dict): build result description.

  Returns:
    Canceled Build.
  """
  identity_str = auth.get_current_identity().to_bytes()

  @ndb.tasklet
  def get_bundle_async(check_access):
    bundle = yield model.BuildBundle.get_async(build_id, infra=True)
    if not bundle:
      raise errors.BuildNotFoundError()
    build = bundle.build
    if check_access and not (yield user.can_cancel_build_async(build)):
      raise user.current_identity_cannot('cancel build %s', build.key.id())
    if build.proto.status == common_pb2.CANCELED:
      raise ndb.Return(bundle, False)
    if build.is_ended:
      raise errors.BuildIsCompletedError('Cannot cancel a completed build')
    raise ndb.Return(bundle, True)

  @ndb.transactional_tasklet
  def txn_async():
    bundle, should_update = yield get_bundle_async(False)
    if not should_update:  # pragma: no cover
      raise ndb.Return(bundle, False)
    now = utils.utcnow()
    build = bundle.build
    build.proto.status = common_pb2.CANCELED
    build.status_changed_time = now
    build.result_details = result_details
    build.proto.summary_markdown = summary_markdown
    build.proto.canceled_by = identity_str
    build.proto.end_time.FromDatetime(now)
    build.clear_lease()
    futs = [
        build.put_async(),
        events.on_build_completing_async(build),
        _put_output_properties_async(build.key, result_details),
        model.BuildSteps.cancel_incomplete_steps_async(
            build.key.id(), build.proto.end_time
        )
    ]

    sw = bundle.infra.parse().swarming
    # TODO(nodir): remove, in favor of swarming.TaskSyncBuild.
    if sw.hostname and sw.task_id:  # pragma: no branch
      futs.append(
          swarming.cancel_task_transactionally_async(sw.hostname, sw.task_id)
      )
    yield futs
    raise ndb.Return(bundle, True)

  bundle, should_update = yield get_bundle_async(True)
  if should_update:
    bundle, updated = yield txn_async()
    if updated:  # pragma: no branch
      events.on_build_completed(bundle.build)
  raise ndb.Return(bundle.build)


def delete_many_builds(bucket_id, status, tags=None, created_by=None):
  if status not in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED):
    raise errors.InvalidInputError(
        'status can be STARTED or SCHEDULED, not %s' % status
    )
  if not user.can_delete_scheduled_builds_async(bucket_id).get_result():
    raise user.current_identity_cannot('delete builds of %s', bucket_id)
  # Validate created_by prior scheduled a push task.
  created_by = user.parse_identity(created_by)
  deferred.defer(
      _task_delete_many_builds,
      bucket_id,
      status,
      tags=tags,
      created_by=created_by,
      # Schedule it on the backend module of the same version.
      # This assumes that both frontend and backend are uploaded together.
      _target='%s.backend' % modules.get_current_version_name(),
      # Retry immediatelly.
      _retry_options=taskqueue.TaskRetryOptions(
          min_backoff_seconds=0,
          max_backoff_seconds=1,
      ),
  )


def _task_delete_many_builds(bucket_id, status, tags=None, created_by=None):

  @ndb.transactional_tasklet
  def txn(key):
    bundle = yield model.BuildBundle.get_async(key.id(), infra=True)
    if not bundle or bundle.build.status_legacy != status:  # pragma: no cover
      raise ndb.Return(False)
    futs = [key.delete_async()]

    sw = bundle.infra.parse().swarming
    if sw.hostname and sw.task_id:  # pragma: no branch
      futs.append(
          swarming.cancel_task_transactionally_async(sw.hostname, sw.task_id)
      )
    yield futs
    raise ndb.Return(True)

  @ndb.tasklet
  def del_if_unchanged(key):
    if (yield txn(key)):  # pragma: no branch
      logging.debug('Deleted %s', key.id())

  assert status in (model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED)
  tags = tags or []
  created_by = user.parse_identity(created_by)
  q = model.Build.query(
      model.Build.bucket_id == bucket_id, model.Build.status_legacy == status
  )
  for t in tags:
    q = q.filter(model.Build.tags == t)
  if created_by:
    q = q.filter(model.Build.created_by == created_by)
  q.map(del_if_unchanged, keys_only=True)


def _reject_swarming_bucket(bucket_id):
  config.validate_bucket_id(bucket_id)
  _, cfg = config.get_bucket(bucket_id)
  assert cfg, 'permission check should have failed'
  if config.is_swarming_config(cfg):
    raise errors.InvalidInputError('Invalid operation on a Swarming bucket')


def pause(bucket_id, is_paused):
  if not user.can_pause_buckets_async(bucket_id).get_result():
    raise user.current_identity_cannot('pause bucket of %s', bucket_id)

  _reject_swarming_bucket(bucket_id)

  @ndb.transactional
  def try_set_pause():
    state = (
        model.BucketState.get_by_id(bucket_id) or
        model.BucketState(id=bucket_id)
    )
    if state.is_paused != is_paused:
      state.is_paused = is_paused
      state.put()

  try_set_pause()


def _fut_results(*futures):
  return [f.get_result() for f in futures]
