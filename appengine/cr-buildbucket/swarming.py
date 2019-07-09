# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module integrates buildbucket with swarming.

A bucket config may have "swarming" field that specifies how a builder
is mapped to a recipe. If build is scheduled for a bucket/builder
with swarming configuration, the integration overrides the default behavior.

Prior adding Build to the datastore, a swarming task is created. The definition
of the task definition is rendered from a global template. The parameters of the
template are defined by the bucket config and build parameters.

A build may have "swarming" parameter which is a JSON object with keys:
  recipe: JSON object
    revision: revision of the recipe. Will be available in the task template
              as $revision parameter.

When creating a task, a PubSub topic is specified. Swarming will notify on
task status updates to the topic and buildbucket will sync its state.
Eventually both swarming task and buildbucket build will complete.

Swarming does not guarantee notification delivery, so there is also a cron job
that checks task results of all incomplete builds every 10 min.
"""

import base64
import collections
import copy
import datetime
import hashlib
import json
import logging
import posixpath
import random
import re
import string
import uuid

from components import config as component_config
from components import decorators
from components import net
from components import utils
from components.config import validation
from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.protobuf import json_format
import webapp2

from legacy import api_common
from proto import common_pb2
from proto import launcher_pb2
from proto import project_config_pb2
import bbutil
import buildtags
import config
import errors
import events
import flatten_swarmingcfg
import model
import swarmingcfg as swarmingcfg_module
import tokens
import tq
import user

# Name of a push task queue that synchronizes a buildbucket build and a swarming
# task; a push task per build.
SYNC_QUEUE_NAME = 'swarming-build-sync'

_PUBSUB_TOPIC = 'swarming'

# This is the path, relative to the swarming run dir, to the directory that
# contains the mounted swarming named caches. It will be prepended to paths of
# caches defined in swarmbucket configs.
_CACHE_DIR = 'cache'

# This is the path, relative to the swarming run dir, which is where the recipes
# are either checked out, or installed via CIPD package.
_KITCHEN_CHECKOUT = 'kitchen-checkout'

# Directory where user-available packages are installed, such as git.
# Relative to swarming task cwd.
# USER_PACKAGE_DIR and USER_PACKAGE_DIR/bin are prepended to $PATH.
USER_PACKAGE_DIR = 'cipd_bin_packages'

################################################################################
# Creation/cancellation of tasks.


class Error(Exception):
  """Base class for swarmbucket-specific errors."""


class TemplateNotFound(Error):
  """Raised when a task template is not found."""


def _get_task_template(canary):
  """Gets a tuple (template_revision, template_dict).

  Args:
    canary (bool): whether canary template should be returned.

  Returns:
    Tuple (template_revision, template_dict):
      template_revision (str): revision of the template, e.g. commit hash.
      template_dict (dict): parsed template, or None if not found.
        May contain $parameters that must be expanded using format_obj().
  """
  text = None
  revision = None
  if canary:
    logging.warning('using canary swarming task template')
    revision, text = component_config.get_self_config(
        'swarming_task_template_canary.json', store_last_good=True
    )

  if not text:
    revision, text = component_config.get_self_config(
        'swarming_task_template.json', store_last_good=True
    )

  template = json.loads(text)
  template.pop('__comment__', None)
  return revision, template


# Mocked in tests.
def _should_use_canary_template(percentage):  # pragma: no cover
  """Returns True if a canary template should be used.

  This function is non-determinstic.
  """
  return random.randint(0, 99) < percentage


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
          'id': str(build.key.id()),
          'tags': build.tags,
      },
  }


def _create_task_def(build, settings, fake_build):
  """Creates a swarming task definition for the |build|."""
  assert isinstance(build, model.Build), type(build)
  assert build.key and build.key.id(), build.key
  assert build.url, 'build.url should have been initialized'
  assert isinstance(fake_build, bool), type(fake_build)

  task_template_rev, task_template = _get_task_template(build.canary)

  bp = build.proto
  sw = bp.infra.swarming

  # TODO(nodir): remove builder_hash parameter.
  h = hashlib.sha256(build.builder_id).hexdigest()
  task_template_params = {
      'builder_hash': h,
      'build_id': build.key.id(),
      'build_url': build.url,
      'builder': bp.builder.builder,
      'cache_dir': _CACHE_DIR,
      'hostname': app_identity.get_default_version_hostname(),
      'project': build.project,
      'swarming_hostname': build.proto.infra.swarming.hostname,
  }
  extra_swarming_tags = []
  if 'recipe' in bp.input.properties.fields:
    extra_swarming_tags, extra_task_template_params = _setup_recipes(build)
    task_template_params.update(extra_task_template_params)

  # Render task template.
  # Format is
  # https://cs.chromium.org/chromium/infra/luci/appengine/swarming/swarming_rpcs.py?q=NewTaskRequest
  task_template_params = {
      k: v or '' for k, v in task_template_params.iteritems()
  }
  task = format_obj(task_template, task_template_params)

  # Set 'pool_task_template' to match our build's canary status.
  # This can be made unconditional after crbug.com/823434 is closed. Right now
  # we override this with "SKIP" in the templates to allow an atomic transition.
  task.setdefault(
      'pool_task_template', 'CANARY_PREFER' if build.canary else 'CANARY_NEVER'
  )

  task['priority'] = str(build.proto.infra.swarming.priority)

  if sw.task_service_account:  # pragma: no branch
    # Don't pass it if not defined, for backward compatibility.
    task['service_account'] = sw.task_service_account

  task['tags'] = _calc_tags(
      build, extra_swarming_tags, task_template_rev, task.get('tags')
  )

  _setup_swarming_request_task_slices(build, settings, task)

  if not fake_build:  # pragma: no branch | covered by swarmbucketapi_test.py
    _setup_swarming_request_pubsub(task, build)

  return task


def _setup_recipes(build):
  """Initializes a build request using recipes.

  Returns:
    extra_swarming_tags, extra_task_template_params
  """
  exe = build.proto.exe
  props = copy.copy(build.proto.input.properties)

  # TODO(nodir): Remove recipe dependencies from buildbucket.
  assert 'recipe' in props.fields, props
  recipe = props['recipe']

  # In order to allow some builders to behave like other builders, we allow
  # builders to explicitly set buildername.
  # TODO(nodir): delete this "feature".
  if 'buildername' not in props:  # pragma: no branch
    props['buildername'] = build.proto.builder.builder

  props.get_or_create_struct('$recipe_engine/runtime').update({
      'is_luci': True,
      'is_experimental': build.experimental,
  })

  if build.proto.number:  # pragma: no branch
    props['buildnumber'] = build.proto.number

  # Add repository property, for backward compatibility.
  # TODO(crbug.com/877161): remove it.
  if len(build.proto.input.gerrit_changes) == 1:  # pragma: no branch
    cl = build.proto.input.gerrit_changes[0]
    suffix = '-review.googlesource.com'
    if cl.host.endswith(suffix) and cl.project:  # pragma: no branch
      props['repository'] = 'https://%s.googlesource.com/%s' % (
          cl.host[:-len(suffix)], cl.project
      )

  props['$recipe_engine/buildbucket'] = _buildbucket_property(build)
  # TODO(nodir): remove legacy "buildbucket" property.
  props['buildbucket'] = _buildbucket_property_legacy(build)
  extra_task_template_params = {
      'recipe': recipe,
      'properties_json': api_common.properties_to_json(props),
      'checkout_dir': _KITCHEN_CHECKOUT,
  }
  extra_swarming_tags = [
      'recipe_name:%s' % recipe,
      'recipe_package:%s' % exe.cipd_package,
  ]

  return extra_swarming_tags, extra_task_template_params


def _calc_tags(build, extra_swarming_tags, task_template_rev, tags):
  """Calculates the Swarming task request tags to use."""
  tags = set(tags or [])
  tags.add('buildbucket_bucket:%s' % build.bucket_id)
  tags.add('buildbucket_build_id:%s' % build.key.id())
  tags.add(
      'buildbucket_hostname:%s' % app_identity.get_default_version_hostname()
  )
  tags.add('buildbucket_template_canary:%s' % ('1' if build.canary else '0'))
  tags.add('buildbucket_template_revision:%s' % task_template_rev)
  tags.update(extra_swarming_tags)
  tags.update(build.tags)
  return sorted(tags)


def _setup_swarming_request_task_slices(build, settings, task):
  """Mutate the task request with named cache, CIPD packages and (soon) expiring
  dimensions.
  """
  # TODO(maruel): Use textproto once https://crbug.com/913953 is done.
  unexpected = set(task) - {
      '__comment__',
      'name',
      'pool_task_template',
      'priority',
      'service_account',
      'tags',
      'task_slices',
  }
  assert not unexpected, 'Unexpected task keys: %s' % unexpected

  assert len(task[u'task_slices']) == 1, task[u'task_slices']
  base_slice = task[u'task_slices'][0]

  unexpected = set(base_slice) - {
      'expiration_secs',
      'properties',
      'wait_for_capacity',
  }
  assert not unexpected, 'Unexpected slice keys: %s' % unexpected

  base_slice[u'expiration_secs'] = str(build.proto.scheduling_timeout.seconds)

  # Now take a look to generate a fallback! This is done by inspecting the
  # Build named caches for field "wait_for_warm_cache".
  dims = _setup_swarming_props(build, settings, base_slice[u'properties'])

  if dims:
    assert len(dims) <= 6
    # Create a fallback by copying the original task slice, each time adding the
    # corresponding expiration.
    task[u'task_slices'] = []
    base_slice.setdefault(u'wait_for_capacity', False)
    last_exp = 0
    for expiration_secs in sorted(dims):
      t = {
          u'expiration_secs': str(expiration_secs - last_exp),
          u'properties': copy.deepcopy(base_slice[u'properties']),
          u'wait_for_capacity': base_slice[u'wait_for_capacity'],
      }
      last_exp = expiration_secs
      task[u'task_slices'].append(t)
    # Tweak expiration on the base_slice, which is the last slice.
    exp = max(int(base_slice[u'expiration_secs']) - last_exp, 60)
    base_slice[u'expiration_secs'] = str(exp)
    task[u'task_slices'].append(base_slice)

    assert len(task[u'task_slices']) == len(dims) + 1

    # Now add the actual fallback dimensions. They could be either from optional
    # named caches or from buildercfg dimensions in the form
    # "<expiration_secs>:<key>:<value>".
    extra_dims = []
    for i, (_expiration_secs, kv) in enumerate(sorted(dims.iteritems(),
                                                      reverse=True)):
      # Now mutate each TaskProperties to have the desired dimensions.
      extra_dims.extend(kv)
      props = task[u'task_slices'][-2 - i][u'properties']
      props[u'dimensions'].extend(extra_dims)
      props[u'dimensions'].sort(key=lambda x: (x[u'key'], x[u'value']))


def _setup_swarming_props(build, settings, props):
  """Fills a TaskProperties.

  Updates props; a python format of TaskProperties.

  Returns:
    dict {expiration_sec: [{'key': key, 'value': value}]} to support caches.
    This is different than the format in flatten_swarmingcfg.parse_dimensions().
  """
  unexpected = set(props) - {
      'caches',
      'cipd_input',
      'command',
      'containment',
      'env_prefixes',
      'execution_timeout_secs',
      'extra_args',
  }
  assert not unexpected, 'Unexpected property keys: %s' % unexpected

  props.setdefault('env', []).append({
      'key': 'BUILDBUCKET_EXPERIMENTAL',
      'value': str(build.experimental).upper(),
  })
  props['cipd_input'] = _compute_cipd_input(build, settings)
  props['execution_timeout_secs'] = str(build.proto.execution_timeout.seconds)

  props['caches'], cache_fallbacks = _setup_named_caches(build)

  # out is dict {expiration_secs: [{'key': key, 'value': value}]}
  out = collections.defaultdict(list)
  for expirations_secs, items in cache_fallbacks.iteritems():
    out[expirations_secs].extend(
        {u'key': u'caches', u'value': item} for item in items
    )

  for d in build.proto.infra.swarming.task_dimensions:
    assert not d.expiration.nanos
    out[d.expiration.seconds].append({u'key': d.key, u'value': d.value})

  props[u'dimensions'] = out.pop(0, [])
  props[u'dimensions'].sort(key=lambda x: (x[u'key'], x[u'value']))
  return out


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
      convert('.', settings.luci_runner_package),
      convert('.', settings.kitchen_package),
      {
          'package_name': build.proto.exe.cipd_package,
          'path': _KITCHEN_CHECKOUT,
          'version': build.proto.exe.cipd_version,
      },
  ]
  for up in settings.user_packages:
    if _builder_matches(build.proto.builder, up.builders):
      path = USER_PACKAGE_DIR
      if up.subdir:
        path = posixpath.join(path, up.subdir)
      packages.append(convert(path, up))
  return {
      'packages': packages,
  }


def _setup_named_caches(build):
  """Computes swarming task caches.

  Returns:
    (cache_list, {expiration_secs: list(caches)}
  """
  caches = []
  cache_fallbacks = collections.defaultdict(list)

  for c in build.proto.infra.swarming.caches:
    if c.path.startswith(u'cache/'):  # pragma: no cover
      # TODO(nodir): remove this code path once clients remove "cache/" from
      # their configs.
      cache_path = c.path
    else:
      cache_path = posixpath.join(_CACHE_DIR, c.path)
    caches.append({u'path': cache_path, u'name': c.name})
    if c.wait_for_warm_cache.seconds:
      cache_fallbacks[c.wait_for_warm_cache.seconds].append(c.name)

  caches.sort(key=lambda p: p.get(u'path'))
  return caches, cache_fallbacks


def _setup_swarming_request_pubsub(task, build):
  """Mutates Swarming task request to add pubsub topic."""
  task['pubsub_topic'] = 'projects/%s/topics/%s' % (
      app_identity.get_application_id(), _PUBSUB_TOPIC
  )
  task['pubsub_userdata'] = json.dumps(
      {
          'build_id': build.key.id(),
          'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
          'swarming_hostname': build.proto.infra.swarming.hostname,
      },
      sort_keys=True,
  )


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


def prepare_task_def(build, settings, fake_build=False):
  """Prepares a swarming task definition.

  Validates the new build.
  Mutates build.
  Creates a swarming task definition.

  The build must have proto.infra initialized.

  Returns a task_def dict.
  """
  assert build.proto.HasField('infra')
  build.url = _generate_build_url(settings.milo_hostname, build)
  task_def = _create_task_def(build, settings, fake_build)
  return task_def


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
  except taskqueue.TaskAlreadyExistsError:  # pragma: no cover
    # Previous attempt for this generation of the task might have already
    # created the next generation task. This is OK.
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

  settings = config.get_settings_async().get_result().swarming

  # Prepare task definition.
  task_def = prepare_task_def(build, settings)

  # Insert secret bytes.
  secrets = launcher_pb2.BuildSecrets(
      build_token=tokens.generate_build_token(build_id, task_key),
  )
  secret_bytes_b64 = base64.b64encode(secrets.SerializeToString())
  for ts in task_def[u'task_slices']:
    ts[u'properties'][u'secret_bytes'] = secret_bytes_b64

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
    for ts in task_def[u'task_slices']:
      ts[u'properties'].pop(u'secret_bytes')
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

    with bundle.infra.mutate() as infra:
      sw = infra.swarming
      if sw.task_id:
        logging.warning('build already has a task %r', sw.task_id)
        return False

      sw.task_id = new_task_id

    # TODO(crbug.com/970053): remove this block once all in-flight and future
    # tasks have BuildInfra entity.
    with build.mutate_infra() as infra:
      sw = infra.swarming
      if sw.task_id:  # pragma: no cover
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

  # TODO(crbug.com/970053): remove this block once all in-flight and future
  # tasks have BuildInfra entity.
  with build.mutate_infra() as infra:
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
    elif state == 'BOT_DIED' or task_result.get('internal_failure'):
      bp.status = common_pb2.INFRA_FAILURE
    elif task_result.get('failure'):
      bp.status = common_pb2.FAILURE
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


def format_obj(obj, params):
  """Evaluates all strings in a JSON-like object as a template."""

  def transform(obj):
    if isinstance(obj, list):
      return map(transform, obj)
    elif isinstance(obj, dict):
      return {k: transform(v) for k, v in obj.iteritems()}
    elif isinstance(obj, basestring):
      return string.Template(obj).safe_substitute(params)
    else:
      return obj

  return transform(obj)


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
