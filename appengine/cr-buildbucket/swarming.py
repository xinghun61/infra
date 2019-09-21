# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module integrates buildbucket with swarming.

A bucket config in cr-buildbucket.cfg may have "swarming" field that specifies
how a builder is mapped to a LUCI executable. If build is scheduled for a bucket
with swarming configuration, the integration overrides the default behavior,
e.g. there is no peeking/leasing of builds.

A push task is recorded transactionally with a build entity. The push task then
creates a swarming task, based on the build proto and global settings, and
re-enqueues itself with 1m delay. Future invocations of the push task
synchronize the build state with the swarming task state (e.g. if a task
starts, then the build is marked as started too) and keep re-enqueuing itself,
with 1m delay, and continuously synchronizes states, until the swarming task
is complete.

When creating a task, a PubSub topic is specified. Swarming will notify on
task status updates to the topic and buildbucket will sync its state.
Eventually both swarming task and buildbucket build will complete.
"""

import base64
import collections
import copy
import datetime
import json
import logging
import posixpath
import re
import uuid

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.protobuf import json_format

import webapp2

from components import decorators
from components import net
from components import utils

from legacy import api_common
from proto import common_pb2
from proto import launcher_pb2
from proto import service_config_pb2
import config
import errors
import events
import model
import tokens
import tq
import user

# Name of a push task queue that synchronizes a buildbucket build and a swarming
# task; a push task per build.
SYNC_QUEUE_NAME = 'swarming-build-sync'

# This is the path, relative to the swarming run dir, to the directory that
# contains the mounted swarming named caches. It will be prepended to paths of
# caches defined in swarmbucket configs.
_CACHE_DIR = 'cache'

# This is the path, relative to the swarming run dir, which is where the recipes
# are either checked out, or installed via CIPD package.
#
# TODO(iannucci): rename this for luci_runner (maybe to "user_exe").
_KITCHEN_CHECKOUT = 'kitchen-checkout'

# Directory where user-available packages are installed, such as git.
# Relative to swarming task cwd.
# USER_PACKAGE_DIR and USER_PACKAGE_DIR/bin are prepended to $PATH.
USER_PACKAGE_DIR = 'cipd_bin_packages'

################################################################################
# Creation/cancellation of tasks.


class Error(Exception):
  """Base class for swarmbucket-specific errors."""


def _buildbucket_property(build):
  """Returns value for '$recipe_engine/buildbucket' build property.

  Code that reads it:
  https://cs.chromium.org/chromium/infra/recipes-py/recipe_modules/buildbucket
  """
  # Exclude some fields from the property.
  export = copy.deepcopy(build.proto)
  export.ClearField('status')
  export.ClearField('update_time')
  export.ClearField('output')
  export.input.ClearField('properties')
  export.infra.ClearField('recipe')
  export.infra.buildbucket.ClearField('requested_properties')
  build.tags_to_protos(export.tags)
  return {
      'build': json_format.MessageToDict(export),
      'hostname': app_identity.get_default_version_hostname(),
  }


def _buildbucket_property_legacy(build):
  """Returns value for 'buildbucket' build property.

  The format of the returned value corresponds the one used in
  buildbot-buildbucket integration [1], with two exceptions:
  - it is not encoded in JSON
  - the list of tags are initial tags only.
    Does not include auto-generated tags.

  [1]:
  https://chromium.googlesource.com/chromium/tools/build/+/82373bb503dca5f91cd0988d49df38394fdf8b0b/scripts/master/buildbucket/integration.py#329
  """
  # TODO(crbug.com/859231): remove this function.
  created_ts = api_common.proto_to_timestamp(build.proto.create_time)
  return {
      'hostname': app_identity.get_default_version_hostname(),
      'build': {
          'project': build.project,
          'bucket': api_common.format_luci_bucket(build.bucket_id),
          'created_by': build.created_by.to_bytes(),
          'created_ts': created_ts,
          'id': str(build.proto.id),
          'tags': build.tags,
      },
  }


def compute_task_def(build, settings, fake_build):
  """Returns a swarming task definition for the |build|.


  Args:
    build (model.Build): the build to generate the task definition for.
      build.proto.infra and build.proto.input.properties must be initialized.
    settings (service_config_pb2.SettingsCfg): global settings.
    fake_build (bool): False if the build is not going to be actually
      created in buildbucket. This is used by led that only needs the definition
      of the task that *would be* used for a new build like this.

  Returns a task_def dict.
  Corresponds to JSON representation of
  https://cs.chromium.org/chromium/infra/luci/appengine/swarming/swarming_rpcs.py?q=NewTaskRequest&sq=package:chromium&g=0&l=438
  """
  assert isinstance(build, model.Build), type(build)
  assert isinstance(fake_build, bool), type(fake_build)
  assert build.proto.HasField('infra')
  assert build.proto.input.HasField('properties')
  assert isinstance(settings, service_config_pb2.SettingsCfg)

  sw = build.proto.infra.swarming

  task = {
      'name': 'bb-%d-%s' % (build.proto.id, build.builder_id),
      'tags': _compute_tags(build),
      'priority': str(sw.priority),
      'task_slices': _compute_task_slices(build, settings),
  }
  if build.proto.number:  # pragma: no branch
    task['name'] += '-%d' % build.proto.number

  if sw.task_service_account:  # pragma: no branch
    # Don't pass it if not defined, for backward compatibility.
    task['service_account'] = sw.task_service_account

  if not fake_build:  # pragma: no branch | covered by swarmbucketapi_test.py
    task['pubsub_topic'] = 'projects/%s/topics/swarming' % (
        app_identity.get_application_id()
    )
    task['pubsub_userdata'] = json.dumps(
        {
            'build_id': build.proto.id,
            'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
            'swarming_hostname': sw.hostname,
        },
        sort_keys=True,
    )

  return task


def _compute_tags(build):
  """Computes the Swarming task request tags to use."""
  logdog = build.proto.infra.logdog
  tags = {
      # TODO(iannucci): remove log_location
      'log_location:logdog://%s/%s/%s/+/annotations' %
      (logdog.hostname, logdog.project, logdog.prefix),
      # TODO(iannucci): remove luci_project.
      'luci_project:%s' % build.proto.builder.project,
      'buildbucket_bucket:%s' % build.bucket_id,
      'buildbucket_build_id:%s' % build.key.id(),
      'buildbucket_hostname:%s' % app_identity.get_default_version_hostname(),
      'buildbucket_template_canary:%s' % ('1' if build.canary else '0'),
  }
  tags.update(build.tags)
  return sorted(tags)


def _compute_task_slices(build, settings):
  """Compute swarming task slices."""

  # {expiration_secs: [{'key': key, 'value': value}]}
  dims = collections.defaultdict(list)
  for c in build.proto.infra.swarming.caches:
    assert not c.wait_for_warm_cache.nanos
    if c.wait_for_warm_cache.seconds:
      dims[c.wait_for_warm_cache.seconds].append({
          'key': 'caches', 'value': c.name
      })
  for d in build.proto.infra.swarming.task_dimensions:
    assert not d.expiration.nanos
    dims[d.expiration.seconds].append({'key': d.key, 'value': d.value})

  dim_key = lambda x: (x['key'], x['value'])
  base_dims = dims.pop(0, [])
  base_dims.sort(key=dim_key)

  base_slice = {
      'expiration_secs': str(build.proto.scheduling_timeout.seconds),
      'wait_for_capacity': False,
      'properties': {
          'cipd_input':
              _compute_cipd_input(build, settings),
          'execution_timeout_secs':
              str(build.proto.execution_timeout.seconds),
          'caches': [{
              'path': posixpath.join(_CACHE_DIR, c.path), 'name': c.name
          } for c in build.proto.infra.swarming.caches],
          'dimensions':
              base_dims,
          'env_prefixes':
              _compute_env_prefixes(build, settings),
          'env': [{
              'key': 'BUILDBUCKET_EXPERIMENTAL',
              'value': str(build.experimental).upper(),
          }],
          'command':
              _compute_command(build, settings),
      },
  }

  if not dims:
    return [base_slice]

  assert len(dims) <= 6, dims  # Swarming limitation
  # Create a fallback by copying the original task slice, each time adding the
  # corresponding expiration.
  task_slices = []
  last_exp = 0
  for expiration_secs in sorted(dims):
    t = {
        'expiration_secs': str(expiration_secs - last_exp),
        'properties': copy.deepcopy(base_slice['properties']),
    }
    last_exp = expiration_secs
    task_slices.append(t)

  # Tweak expiration on the base_slice, which is the last slice.
  exp = max(int(base_slice['expiration_secs']) - last_exp, 60)
  base_slice['expiration_secs'] = str(exp)
  task_slices.append(base_slice)

  assert len(task_slices) == len(dims) + 1

  # Now add the actual fallback dimensions.
  extra_dims = []
  for i, (_expiration_secs, kv) in enumerate(sorted(dims.iteritems(),
                                                    reverse=True)):
    # Now mutate each TaskProperties to have the desired dimensions.
    extra_dims.extend(kv)
    props = task_slices[-2 - i]['properties']
    props['dimensions'].extend(extra_dims)
    props['dimensions'].sort(key=dim_key)
  return task_slices


def _compute_env_prefixes(build, settings):
  """Returns env_prefixes key in swarming properties."""
  env_prefixes = {
      'PATH': [
          USER_PACKAGE_DIR,
          posixpath.join(USER_PACKAGE_DIR, 'bin'),
      ],
  }
  extra_paths = set()
  for up in settings.swarming.user_packages:
    if up.subdir:
      path = posixpath.join(USER_PACKAGE_DIR, up.subdir)
      extra_paths.add(path)
      extra_paths.add(posixpath.join(path, 'bin'))
  env_prefixes['PATH'].extend(sorted(extra_paths))
  for c in build.proto.infra.swarming.caches:
    if c.env_var:
      prefixes = env_prefixes.setdefault(c.env_var, [])
      prefixes.append(posixpath.join(_CACHE_DIR, c.path))

  return [{
      'key': key,
      'value': value,
  } for key, value in sorted(env_prefixes.iteritems())]


def _compute_cipd_input(build, settings):
  """Returns swarming task CIPD input."""

  def convert(path, pkg):
    """Converts a package from settings to swarming."""
    version = pkg.version
    if pkg.version_canary and build.proto.canary:
      version = pkg.version_canary
    return {
        'package_name': pkg.package_name,
        'path': path,
        'version': version,
    }

  packages = [
      convert('.', settings.swarming.luci_runner_package),
      convert('.', settings.swarming.kitchen_package),
      {
          'package_name': build.proto.exe.cipd_package,
          'path': _KITCHEN_CHECKOUT,
          'version': build.proto.exe.cipd_version,
      },
  ]
  for up in settings.swarming.user_packages:
    if _builder_matches(build.proto.builder, up.builders):
      path = USER_PACKAGE_DIR
      if up.subdir:
        path = posixpath.join(path, up.subdir)
      packages.append(convert(path, up))
  return {
      'packages': packages,
  }


def _compute_command(build, settings):
  if _builder_matches(build.proto.builder,
                      settings.swarming.luci_runner_package.builders):
    return _compute_luci_runner(build, settings)

  logdog = build.proto.infra.logdog
  annotation_url = (
      'logdog://%s/%s/%s/+/annotations' %
      (logdog.hostname, logdog.project, logdog.prefix)
  )
  ret = [
      'kitchen${EXECUTABLE_SUFFIX}',
      'cook',
      '-buildbucket-hostname',
      app_identity.get_default_version_hostname(),
      '-buildbucket-build-id',
      build.proto.id,
      '-call-update-build',
      '-build-url',
      _generate_build_url(settings.swarming.milo_hostname, build),
      '-luci-system-account',
      'system',
      '-recipe',
      build.proto.input.properties['recipe'],
      '-cache-dir',
      _CACHE_DIR,
      '-checkout-dir',
      _KITCHEN_CHECKOUT,
      '-temp-dir',
      'tmp',
      '-properties',
      api_common.properties_to_json(_compute_legacy_properties(build)),
      '-logdog-annotation-url',
      annotation_url,
  ]
  for h in settings.known_public_gerrit_hosts:
    ret += ['-known-gerrit-host', h]

  ret = map(unicode, ret)  # Ensure strings.
  return ret


def _compute_legacy_properties(build):
  """Returns a Struct of properties to be sent to the swarming task.

  Mostly provides backward compatibility.
  """
  # This is a recipe-based builder. We need to mutate the properties
  # to account for backward compatibility.
  ret = copy.copy(build.proto.input.properties)

  ret.update({
      # TODO(crbug.com/877161): remove legacy "buildername" property.
      'buildername': build.proto.builder.builder,
      '$recipe_engine/buildbucket': _buildbucket_property(build),
      # TODO(crbug.com/877161): remove legacy "buildbucket" property.
      'buildbucket': _buildbucket_property_legacy(build),
  })

  ret.get_or_create_struct('$recipe_engine/runtime').update({
      'is_luci': True,
      'is_experimental': build.experimental,
  })

  if build.proto.number:  # pragma: no branch
    ret['buildnumber'] = build.proto.number

  # Add repository property, for backward compatibility.
  # TODO(crbug.com/877161): remove it.
  if len(build.proto.input.gerrit_changes) == 1:  # pragma: no branch
    cl = build.proto.input.gerrit_changes[0]
    suffix = '-review.googlesource.com'
    if cl.host.endswith(suffix) and cl.project:  # pragma: no branch
      ret['repository'] = 'https://%s.googlesource.com/%s' % (
          cl.host[:-len(suffix)], cl.project
      )

  return ret


# Strip newlines and end padding characters.
_CLI_ENCODED_STRIP_RE = re.compile('\n|=')


def _cli_encode_proto(message):
  """Encodes a proto message for use on the luci_runner command line."""
  raw = message.SerializeToString().encode('zlib').encode('base64')
  return _CLI_ENCODED_STRIP_RE.sub('', raw)


def _compute_luci_runner(build, settings):
  """Returns the command for luci_runner."""
  args = launcher_pb2.RunnerArgs(
      buildbucket_host=app_identity.get_default_version_hostname(),
      logdog_host=build.proto.infra.logdog.hostname,
      executable_dir=_KITCHEN_CHECKOUT,
      cache_dir=_CACHE_DIR,
      known_public_gerrit_hosts=settings.known_public_gerrit_hosts,
      luci_system_account='system',
      build=build.proto,
  )
  return [
      u'luci_runner${EXECUTABLE_SUFFIX}', '-args-b64gz',
      _cli_encode_proto(args)
  ]


def validate_build(build):
  """Raises errors.InvalidInputError if swarming constraints are violated."""
  if build.lease_key:
    raise errors.InvalidInputError(
        'Swarming buckets do not support creation of leased builds'
    )

  expirations = set()
  for dim in build.proto.infra.swarming.task_dimensions:
    assert not dim.expiration.nanos
    expirations.add(dim.expiration.seconds)

  if len(expirations) > 6:
    raise errors.InvalidInputError(
        'swarming supports up to 6 unique expirations'
    )


def create_sync_task(build):  # pragma: no cover
  """Returns def of a push task that maintains build state until it ends.

  Handled by TaskSyncBuild.

  Raises:
    errors.InvalidInputError if the build is invalid.
  """
  validate_build(build)

  payload = {
      'id': build.key.id(),
      'generation': 0,
  }
  return {
      'url': '/internal/task/swarming/sync-build/%s' % build.key.id(),
      'payload': json.dumps(payload, sort_keys=True),
      'retry_options': {'task_age_limit': model.BUILD_TIMEOUT.total_seconds()},
  }


def _sync_build_and_swarming(build_id, generation):
  """Synchronizes build and Swarming.

  If the swarming task does not exist yet, creates it.
  Otherwise updates the build state to match swarming task state.

  Enqueues a new sync push task if the build did not end.
  """
  bundle = model.BuildBundle.get(build_id, infra=True, input_properties=True)
  if not bundle:  # pragma: no cover
    logging.warning('build not found')
    return

  build = bundle.build
  if build.is_ended:
    logging.info('build ended')
    return

  build.proto.infra.ParseFromString(bundle.infra.infra)
  build.proto.input.properties.ParseFromString(
      bundle.input_properties.properties
  )
  sw = build.proto.infra.swarming

  if not sw.task_id:
    _create_swarming_task(build)
  else:
    result = _load_task_result(sw.hostname, sw.task_id)
    if not result:
      logging.error(
          'Task %s/%s referenced by build %s is not found', sw.hostname,
          sw.task_id, build.key.id()
      )
    _sync_build_with_task_result(build_id, result)

  # Enqueue a continuation task.
  next_gen = generation + 1
  payload = {
      'id': build.key.id(),
      'generation': next_gen,
  }
  deadline = build.create_time + model.BUILD_TIMEOUT
  age_limit = deadline - utils.utcnow()
  continuation = {
      'name': 'sync-task-%d-%d' % (build_id, next_gen),
      'url': '/internal/task/swarming/sync-build/%s' % build.key.id(),
      'payload': json.dumps(payload, sort_keys=True),
      'retry_options': {'task_age_limit': age_limit.total_seconds()},
      'countdown': 60,  # Run the continuation task in 1m.
  }
  try:
    tq.enqueue_async(
        SYNC_QUEUE_NAME, [continuation], transactional=False
    ).get_result()
  except (taskqueue.TaskAlreadyExistsError,
          taskqueue.TombstonedTaskError):  # pragma: no cover
    # Previous attempt for this generation of the task might have already
    # created the next generation task, and in case of TombstonedTaskError this
    # task may be already executing or even finished. This is OK.
    pass


def _create_swarming_task(build):
  """Creates a swarming task for the build.

  Requires build.proto.input.properties and build.proto.infra to be populated.
  """
  assert build.proto.HasField('infra')
  assert build.proto.input.HasField('properties')
  sw = build.proto.infra.swarming
  logging.info('creating a task on %s', sw.hostname)
  build_id = build.proto.id

  task_key = str(uuid.uuid4())

  settings = config.get_settings_async().get_result()

  # Prepare task definition.
  task_def = compute_task_def(build, settings, fake_build=False)

  # Insert secret bytes.
  secrets = launcher_pb2.BuildSecrets(
      build_token=tokens.generate_build_token(build_id, task_key),
  )
  secret_bytes_b64 = base64.b64encode(secrets.SerializeToString())
  for ts in task_def['task_slices']:
    ts['properties']['secret_bytes'] = secret_bytes_b64

  new_task_id = None
  try:
    res = _call_api_async(
        impersonate=True,
        hostname=sw.hostname,
        path='tasks/new',
        method='POST',
        payload=task_def,
        delegation_identity=build.created_by,
        # Make Swarming know what bucket the task belong too. Swarming uses
        # this to authorize access to pools assigned to specific buckets only.
        delegation_tag='buildbucket:bucket:%s' % build.bucket_id,
        deadline=30,
        # Try only once so we don't have multiple swarming tasks with same
        # task_key and valid token, otherwise they will race.
        max_attempts=1,
    ).get_result()
    new_task_id = res['task_id']
    assert new_task_id
    logging.info('Created a swarming task %r', new_task_id)
  except net.Error as err:
    if err.status_code >= 500 or err.status_code is None:
      raise

    # Dump the task definition to the log.
    # Pop secret bytes.
    for ts in task_def['task_slices']:
      ts['properties'].pop('secret_bytes')
    logging.error(
        (
            'Swarming responded with HTTP %d. '
            'Ending the build with INFRA_FAILURE.\n'
            'Task def: %s\n'
            'Response: %s'
        ),
        err.status_code,
        task_def,
        err.response,
    )
    _end_build(
        build_id,
        common_pb2.INFRA_FAILURE,
        (
            'Swarming task creation API responded with HTTP %d: `%s`' %
            (err.status_code, err.response.replace('`', '"'))
        ),
        end_time=utils.utcnow(),
    )
    return

  # Task was created.

  @ndb.transactional
  def txn():
    bundle = model.BuildBundle.get(build_id, infra=True)
    if not bundle:  # pragma: no cover
      return False
    build = bundle.build

    with bundle.infra.mutate() as infra:
      sw = infra.swarming
      if sw.task_id:
        logging.warning('build already has a task %r', sw.task_id)
        return False

      sw.task_id = new_task_id

    assert not build.swarming_task_key
    build.swarming_task_key = task_key
    bundle.put()
    return True

  updated = False
  try:
    updated = txn()
  finally:
    if not updated:
      logging.error(
          'created a task, but did not update datastore.\n'
          'canceling task %s, best effort',
          new_task_id,
      )
      cancel_task(sw.hostname, new_task_id)


class TaskSyncBuild(webapp2.RequestHandler):  # pragma: no cover
  """Sync a LUCI build with swarming."""

  @decorators.require_taskqueue(SYNC_QUEUE_NAME)
  def post(self, build_id):  # pylint: disable=unused-argument
    body = json.loads(self.request.body)
    _sync_build_and_swarming(body['id'], body['generation'])


def _generate_build_url(milo_hostname, build):
  if not milo_hostname:
    sw = build.proto.infra.swarming
    return 'https://%s/task?id=%s' % (sw.hostname, sw.task_id)

  return 'https://%s/b/%d' % (milo_hostname, build.key.id())


@ndb.tasklet
def cancel_task_async(hostname, task_id):
  """Cancels a swarming task.

  Noop if the task started running.
  """
  res = yield _call_api_async(
      impersonate=False,
      hostname=hostname,
      path='task/%s/cancel' % task_id,
      method='POST',
      payload={
          'kill_running': True,
      },
  )

  if res.get('ok'):
    logging.info('response: %r', res)
  else:
    logging.warning('response: %r', res)


def cancel_task(hostname, task_id):
  """Sync version of cancel_task_async.

  Noop if the task started running.
  """
  cancel_task_async(hostname, task_id).get_result()


@ndb.tasklet
def cancel_task_transactionally_async(hostname, task_id):  # pragma: no cover
  """Transactionally schedules a push task to cancel a swarming task.

  Swarming task cancelation is noop if the task started running.
  """
  url = (
      '/internal/task/buildbucket/cancel_swarming_task/%s/%s' %
      (hostname, task_id)
  )
  task = taskqueue.Task(url=url)
  res = yield task.add_async(queue_name='backend-default', transactional=True)
  raise ndb.Return(res)


################################################################################
# Update builds.


def _load_task_result(hostname, task_id):  # pragma: no cover
  return _call_api_async(
      impersonate=False,
      hostname=hostname,
      path='task/%s/result' % task_id,
  ).get_result()


def _sync_build_with_task_result_in_memory(build, build_infra, task_result):
  """Syncs buildbucket |build| state with swarming task |result|.

  Mutates build only if status has changed. Returns True in that case.

  If task_result is None, marks the build as INFRA_FAILURE.
  """

  # Task result docs:
  # https://github.com/luci/luci-py/blob/985821e9f13da2c93cb149d9e1159c68c72d58da/appengine/swarming/server/task_result.py#L239

  if build.is_ended:  # pragma: no cover
    # Completed builds are immutable.
    return False

  now = utils.utcnow()
  old_status = build.proto.status
  bp = build.proto

  with build_infra.mutate() as infra:
    sw = infra.swarming
    sw.ClearField('bot_dimensions')
    for d in (task_result or {}).get('bot_dimensions', []):
      assert isinstance(d['value'], list)
      for v in d['value']:
        sw.bot_dimensions.add(key=d['key'], value=v)
    sw.bot_dimensions.sort(key=lambda d: (d.key, d.value))

  terminal_states = {
      'EXPIRED',
      'TIMED_OUT',
      'BOT_DIED',
      'CANCELED',
      'COMPLETED',
      'KILLED',
      'NO_RESOURCE',
  }
  state = (task_result or {}).get('state')
  if state is None:
    bp.status = common_pb2.INFRA_FAILURE
    bp.summary_markdown = (
        'Swarming task %s on %s unexpectedly disappeared' %
        (sw.task_id, sw.hostname)
    )
  elif state == 'PENDING':
    if bp.status == common_pb2.STARTED:  # pragma: no cover
      # Most probably, race between PubSub push handler and Cron job.
      # With swarming, a build cannot go from STARTED back to PENDING,
      # so ignore this.
      return False
    bp.status = common_pb2.SCHEDULED
  elif state == 'RUNNING':
    bp.status = common_pb2.STARTED
  elif state in terminal_states:
    if state in ('CANCELED', 'KILLED'):
      bp.status = common_pb2.CANCELED
    elif state == 'NO_RESOURCE':
      # Task did not start.
      bp.status = common_pb2.INFRA_FAILURE
      bp.status_details.resource_exhaustion.SetInParent()
    elif state == 'EXPIRED':
      # Task did not start.
      bp.status = common_pb2.INFRA_FAILURE
      bp.status_details.resource_exhaustion.SetInParent()
      bp.status_details.timeout.SetInParent()
    elif state == 'TIMED_OUT':
      # Task started, but timed out.
      bp.status = common_pb2.INFRA_FAILURE
      bp.status_details.timeout.SetInParent()
    elif state == 'BOT_DIED' or task_result.get('failure'):
      # If this truly was a non-infra failure, luci_runner would catch that and
      # mark the build as FAILURE.
      # That did not happen, so this is an infra failure.
      bp.status = common_pb2.INFRA_FAILURE
    else:
      assert state == 'COMPLETED'
      bp.status = common_pb2.SUCCESS
  else:  # pragma: no cover
    assert False, 'Unexpected task state: %s' % state

  if bp.status == old_status:  # pragma: no cover
    return False
  build.status_changed_time = now
  logging.info(
      'Build %s status: %s -> %s', build.key.id(), old_status, bp.status
  )

  def ts(key):
    v = (task_result or {}).get(key)
    return _parse_ts(v) if v else None

  if bp.status == common_pb2.STARTED:
    bp.start_time.FromDatetime(ts('started_ts') or now)
  elif build.is_ended:  # pragma: no branch
    logging.info('Build %s result: %s', build.key.id(), build.result)

    started_ts = ts('started_ts')
    if started_ts:
      bp.start_time.FromDatetime(started_ts)
    bp.end_time.FromDatetime(ts('completed_ts') or ts('abandoned_ts') or now)

    # It is possible that swarming task was marked as NO_RESOURCE the moment
    # it was created. Swarming VM time is not synchronized with buildbucket VM
    # time, so adjust end_time if needed.
    if bp.end_time.ToDatetime() < bp.create_time.ToDatetime():
      bp.end_time.CopyFrom(bp.create_time)
  return True


def _sync_build_with_task_result(build_id, task_result):
  """Syncs Build entity in the datastore with a result of the swarming task."""

  @ndb.transactional
  def txn():
    bundle = model.BuildBundle.get(build_id, infra=True)
    if not bundle:  # pragma: no cover
      return None
    build = bundle.build
    status_changed = _sync_build_with_task_result_in_memory(
        build, bundle.infra, task_result
    )
    if not status_changed:
      return None

    futures = [bundle.put_async()]

    if build.proto.status == common_pb2.STARTED:
      futures.append(events.on_build_starting_async(build))
    elif build.is_ended:  # pragma: no branch
      futures.append(
          model.BuildSteps.cancel_incomplete_steps_async(
              build_id, build.proto.end_time
          )
      )
      futures.append(events.on_build_completing_async(build))

    for f in futures:
      f.check_success()
    return build

  build = txn()
  if build:
    if build.proto.status == common_pb2.STARTED:
      events.on_build_started(build)
    elif build.is_ended:  # pragma: no branch
      events.on_build_completed(build)


class SubNotify(webapp2.RequestHandler):
  """Handles PubSub messages from swarming.

  Assumes unprivileged users cannot send requests to this handler.
  """

  bad_message = False

  def unpack_msg(self, msg):
    """Extracts swarming hostname, creation time, task id and build id from msg.

    Aborts if |msg| is malformed.
    """
    data_b64 = msg.get('data')
    if not data_b64:
      self.stop('no message data')
    try:
      data_json = base64.b64decode(data_b64)
    except ValueError as ex:  # pragma: no cover
      self.stop('cannot decode message data as base64: %s', ex)
    data = self.parse_json_obj(data_json, 'message data')
    userdata = self.parse_json_obj(data.get('userdata'), 'userdata')

    hostname = userdata.get('swarming_hostname')
    if not hostname:
      self.stop('swarming hostname not found in userdata')
    if not isinstance(hostname, basestring):
      self.stop('swarming hostname is not a string')

    created_ts = userdata.get('created_ts')
    if not created_ts:
      self.stop('created_ts not found in userdata')
    try:
      created_time = utils.timestamp_to_datetime(created_ts)
    except ValueError as ex:
      self.stop('created_ts in userdata is invalid: %s', ex)

    build_id = userdata.get('build_id')
    if not isinstance(build_id, (int, long)):
      self.stop('invalid build_id %r', build_id)

    task_id = data.get('task_id')
    if not task_id:
      self.stop('task_id not found in message data')

    return hostname, created_time, task_id, build_id

  def post(self):
    msg = self.request.json['message']
    logging.info('Received message: %r', msg)

    # Try not to process same message more than once.
    nc = 'swarming-pubsub-msg-id'
    if memcache.get(msg['messageId'], namespace=nc):
      logging.info('seen this message before, ignoring')
    else:
      self._process_msg(msg)
    memcache.set(msg['messageId'], 1, namespace=nc, time=10 * 60)

  def _process_msg(self, msg):
    hostname, created_time, task_id, build_id = self.unpack_msg(msg)
    task_url = 'https://%s/task?id=%s' % (hostname, task_id)

    # Load build.
    logging.info('Build id: %s', build_id)
    bundle = model.BuildBundle.get(build_id, infra=True)
    if not bundle:

      # TODO(nodir): remove this if statement.

      fresh = utils.utcnow() < created_time + datetime.timedelta(minutes=1)
      if fresh:  # pragma: no cover
        self.stop(
            'Build for a swarming task not found yet\nBuild: %s\nTask: %s',
            build_id,
            task_url,
            redeliver=True
        )
      self.stop(
          'Build for a swarming task not found\nBuild: %s\nTask: %s', build_id,
          task_url
      )

    # Ensure the loaded build is associated with the task.
    sw = bundle.infra.parse().swarming
    if hostname != sw.hostname:
      self.stop(
          'swarming_hostname %s of build %s does not match %s', sw.hostname,
          build_id, hostname
      )
    if not sw.task_id:
      self.stop('build is not associated with a task yet', redeliver=True)
    if task_id != sw.task_id:
      self.stop(
          'swarming_task_id %s of build %s does not match %s', sw.task_id,
          build_id, task_id
      )

    # Update build.
    result = _load_task_result(hostname, task_id)
    _sync_build_with_task_result(build_id, result)

  def stop(self, msg, *args, **kwargs):
    """Logs error and stops request processing.

    Args:
      msg: error message
      args: format args for msg.
      kwargs:
        redeliver: True to process this message later.
    """
    self.bad_message = True
    if args:
      msg = msg % args
    redeliver = kwargs.get('redeliver')
    logging.log(logging.WARNING if redeliver else logging.ERROR, msg)
    self.response.write(msg)
    self.abort(400 if redeliver else 200)

  def parse_json_obj(self, text, name):
    """Parses a JSON object from |text| if possible. Otherwise stops."""
    try:
      result = json.loads(text or '')
      if not isinstance(result, dict):
        raise ValueError()
      return result
    except ValueError:
      self.stop('%s is not a valid JSON object: %r', name, text)


def get_backend_routes():  # pragma: no cover
  return [
      webapp2.Route(
          r'/internal/task/swarming/sync-build/<build_id:\d+>', TaskSyncBuild
      ),
      webapp2.Route(r'/_ah/push-handlers/swarming/notify', SubNotify),
  ]


################################################################################
# Utility functions


@ndb.tasklet
def _call_api_async(
    impersonate,
    hostname,
    path,
    method='GET',
    payload=None,
    delegation_tag=None,
    delegation_identity=None,
    deadline=None,
    max_attempts=None,
):
  """Calls Swarming API."""
  delegation_token = None
  if impersonate:
    delegation_token = yield user.delegate_async(
        hostname, identity=delegation_identity, tag=delegation_tag
    )
  url = 'https://%s/_ah/api/swarming/v1/%s' % (hostname, path)
  res = yield net.json_request_async(
      url,
      method=method,
      payload=payload,
      scopes=net.EMAIL_SCOPE,
      deadline=deadline,
      max_attempts=max_attempts,
      delegation_token=delegation_token,
  )
  raise ndb.Return(res)


def _parse_ts(ts):
  """Parses Swarming API's timestamp, which is RFC3339 without time zone."""

  # time-secfrac part of RFC3339 format is optional
  # https://tools.ietf.org/html/rfc3339#section-5.6
  # strptime cannot handle optional parts.
  # HACK: add the time-secfrac part if it is missing.
  # P(time-secfrac is missing) = 1e-6.
  if '.' not in ts:  # pragma: no cover
    ts += '.0'
  return datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%f')


def _end_build(build_id, status, summary_markdown='', end_time=None):
  assert model.is_terminal_status(status)
  end_time = end_time or utils.utcnow()

  @ndb.transactional
  def txn():
    build = model.Build.get_by_id(build_id)
    if not build:  # pragma: no cover
      return None

    build.proto.status = status
    build.proto.summary_markdown = summary_markdown
    build.proto.end_time.FromDatetime(end_time)
    ndb.Future.wait_all([
        build.put_async(),
        events.on_build_completing_async(build)
    ])
    return build

  build = txn()
  if build:  # pragma: no branch
    events.on_build_completed(build)


def _builder_matches(builder_id, predicate):
  bs = config.builder_id_string(builder_id)

  def matches(regex_list):
    for r in regex_list:
      try:
        if re.match('^%s$' % r, bs):
          return True
      except re.error:  # pragma: no cover
        logging.exception('Regex %r failed on %r', r, bs)
    return False

  if matches(predicate.regex_exclude):
    return False
  return not predicate.regex or matches(predicate.regex)
