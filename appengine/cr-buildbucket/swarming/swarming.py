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
import copy
import datetime
import hashlib
import json
import logging
import posixpath
import random
import string

from components import auth
from components import config as component_config
from components import decorators
from components import net
from components import utils
from components.config import validation
from google.appengine.api import app_identity
from google.appengine.ext import ndb
import webapp2

from proto import project_config_pb2
from proto import service_config_pb2
from . import swarmingcfg as swarmingcfg_module
from . import isolate
import config
import errors
import events
import model
import protoutil
import sequence

PUBSUB_TOPIC = 'swarming'
BUILDER_PARAMETER = 'builder_name'
PARAM_PROPERTIES = 'properties'
PARAM_SWARMING = 'swarming'
PARAM_CHANGES = 'changes'
BUILD_RUN_RESULT_FILENAME = 'build-run-result.json'

# The default percentage of builds that use canary swarming task template.
# This number is relatively high so we treat canary seriously and that we have
# a strong signal if the canary is broken.
# If it is, the template must be reverted to a stable version ASAP.
DEFAULT_CANARY_TEMPLATE_PERCENTAGE = 10

# This is the path, relative to swarming run dir, to the directory that contains
# symlinks to swarming named caches. It will be prepended to paths of caches
# defined in swarmbucket configs.
CACHE_DIR = 'cache'


################################################################################
# Creation/cancellation of tasks.

class Error(Exception):
  """Base class for swarmbucket-specific errors."""


class TemplateNotFound(Error):
  """Raised when a task template is not found."""


class CanaryTemplateNotFound(TemplateNotFound):
  """Raised when canary template is explicitly requested, but not found."""


class BuildResultFileCorruptedError(Error):
  """Raised when build result file or its containing isolate is corrupted."""


@ndb.tasklet
def get_settings_async():  # pragma: no cover
  _, global_settings = yield component_config.get_self_config_async(
      'settings.cfg',
      service_config_pb2.SettingsCfg,
      store_last_good=True)
  global_settings = global_settings or service_config_pb2.SettingsCfg()
  raise ndb.Return(global_settings.swarming)


@ndb.tasklet
def get_task_template_async(canary, canary_required=True):
  """Gets a tuple (template_revision, template_dict, canary_bool).

  Args:
    canary (bool): specifies a whether canary template should be returned.
    canary_required (bool): controls the behavior if |canary| is True and
      the canary template is not found. If False use the non-canary template,
      otherwise raise CanaryTemplateNotFound.
      Ignored if canary is False.

  Returns:
    Tuple (template_revision, template_dict, canary):
      template_revision (str): revision of the template, e.g. commit hash.
      template_dict (dict): parsed template, or None if not found.
        May contain $parameters that must be expanded using format_obj().
      canary (bool): True if the returned template is a canary template.
  """
  text = None
  revision = None
  if canary:
    logging.warning('using canary swarming task template')
    revision, text = yield component_config.get_self_config_async(
        'swarming_task_template_canary.json', store_last_good=True)
    canary = bool(text)
    if not text:
      if canary_required:
        raise CanaryTemplateNotFound(
            'canary swarming task template is requested, '
            'but the canary template is not found')
      logging.warning(
          'canary swarming task template is not found. using the default one')

  if not text:
    revision, text = yield component_config.get_self_config_async(
        'swarming_task_template.json', store_last_good=True)

  template = None
  if text:
    template = json.loads(text)
    template.pop('__comment__', None)
  raise ndb.Return(revision, template, canary)


def validate_build_parameters(builder_name, params):
  """Raises errors.InvalidInputError if build parameters are invalid."""
  params = copy.deepcopy(params)

  def bad(fmt, *args):
    raise errors.InvalidInputError(fmt % args)

  params.pop(BUILDER_PARAMETER)  # already validated

  def assert_object(name, value):
    if not isinstance(value, dict):
      bad('%s parameter must be an object' % name)

  properties = params.pop(PARAM_PROPERTIES, None)
  if properties is not None:
    assert_object('properties', properties)
    if properties.get('buildername', builder_name) != builder_name:
      bad('inconsistent builder name')

  swarming = params.pop(PARAM_SWARMING, None)
  if swarming is not None:
    assert_object('swarming', swarming)
    swarming = copy.deepcopy(swarming)

    override_builder_cfg_data = swarming.pop('override_builder_cfg', None)
    if override_builder_cfg_data is not None:
      assert_object('swarming.override_builder_cfg', override_builder_cfg_data)
      if 'build_numbers' in override_builder_cfg_data:
        bad(
            'swarming.override_builder_cfg parameter '
            'cannot override build_numbers')

      override_builder_cfg = project_config_pb2.Builder()
      try:
        protoutil.merge_dict(
            override_builder_cfg_data, override_builder_cfg)
      except TypeError as ex:
        bad('swarming.override_builder_cfg parameter: %s', ex)
      if override_builder_cfg.name:
        bad('swarming.override_builder_cfg cannot override builder name')
      if override_builder_cfg.mixins:
        bad('swarming.override_builder_cfg cannot use mixins')
      ctx = validation.Context.raise_on_error(
          exc_type=errors.InvalidInputError,
          prefix='swarming.override_builder_cfg parameter: ')
      swarmingcfg_module.validate_builder_cfg(
          override_builder_cfg, [], False, ctx)

    if swarming:
      bad('unrecognized keys in swarming param: %r', swarming.keys())

  changes = params.pop(PARAM_CHANGES, None)
  if changes is not None:
    if not isinstance(changes, list):
      bad('changes param must be an array')
    for c in changes:  # pragma: no branch
      if not isinstance(c, dict):
        bad('changes param must contain only objects')
      repo_url = c.get('repo_url')
      if repo_url is not None and not isinstance(repo_url, basestring):
        bad('change repo_url must be a string')
      author = c.get('author')
      if not isinstance(author, dict):
        bad('change author must be an object')
      email = author.get('email')
      if not isinstance(email, basestring):
        bad('change author email must be a string')
      if not email:
        bad('change author email not specified')


# Mocked in tests.
def should_use_canary_template(percentage):  # pragma: no cover
  """Returns True if a canary template should be used.

  This function is non-determinstic.
  """
  return random.randint(0, 99) < percentage


def _prepare_builder_config(builder_cfg, swarming_param):
  """Returns final version of builder config to use for |build|.

  Expects arguments to be valid.
  """
  # Builders are already flattened in the datastore.
  result = builder_cfg

  # Apply overrides in the swarming parameter.
  override_builder_cfg_data = swarming_param.get('override_builder_cfg', {})
  if override_builder_cfg_data:
    override_builder_cfg = project_config_pb2.Builder()
    protoutil.merge_dict(override_builder_cfg_data, result)
    ctx = validation.Context.raise_on_error(
        exc_type=errors.InvalidInputError,
        prefix='swarming.override_buider_cfg parameter: ')
    swarmingcfg_module.merge_builder(result, override_builder_cfg)
    swarmingcfg_module.validate_builder_cfg(result, [], True, ctx)
  return result


def _buildbucket_property(build):
  """Returns value for 'buildbucket' build property.

  The format of the returned value corresponds the one used in
  buildbot-buildbucket integration [1], with two exceptions:
  - it is not encoded in JSON
  - the list of tags are initial tags only.
    Does not include auto-generated tags.

  [1]:
  https://chromium.googlesource.com/chromium/tools/build/+/82373bb503dca5f91cd0988d49df38394fdf8b0b/scripts/master/buildbucket/integration.py#329
  """
  return {
    'hostname': app_identity.get_default_version_hostname(),
    'build': {
      'bucket': build.bucket,
      'created_by': build.created_by.to_bytes(),
      'created_ts': utils.datetime_to_timestamp(build.create_time),
      'id': str(build.key.id()),
      # Note: this includes only user-specified tags.
      # It does not include auto-generated tags, such as "swarming_tag".
      # This is a bit different from Buildbot-Buildbucket integration.
      # In practice, however, only "buildset" tag is read from this list.
      'tags': build.initial_tags,
    },
  }


@ndb.tasklet
def _create_task_def_async(
    project_id, swarming_cfg, builder_cfg, build, build_number, settings,
    fake_build):
  """Creates a swarming task definition for the |build|.

  Supports build properties that are supported by Buildbot-Buildbucket
  integration. See
  https://chromium.googlesource.com/chromium/tools/build/+/eff4ceb/scripts/master/buildbucket/README.md#Build-parameters

  Sets build.swarming_hostname and build.canary attributes.

  Raises:
    errors.InvalidInputError if build.parameters are invalid.
  """
  assert build.key and build.key.id(), build.key
  params = build.parameters or {}
  validate_build_parameters(builder_cfg.name, params)
  swarming_param = params.get(PARAM_SWARMING) or {}

  # Use canary template?
  assert isinstance(build.canary_preference, model.CanaryPreference)
  if build.canary_preference == model.CanaryPreference.AUTO:
    canary_percentage = DEFAULT_CANARY_TEMPLATE_PERCENTAGE
    if swarming_cfg.HasField('task_template_canary_percentage'):
      canary_percentage = swarming_cfg.task_template_canary_percentage.value
    build.canary = should_use_canary_template(canary_percentage)
  else:
    build.canary = build.canary_preference == model.CanaryPreference.CANARY

  builder_cfg = _prepare_builder_config(builder_cfg, swarming_param)

  try:
    task_template_rev, task_template, build.canary = (
        yield get_task_template_async(
            build.canary,
            build.canary_preference == model.CanaryPreference.CANARY))
  except CanaryTemplateNotFound as ex:
    raise errors.InvalidInputError(ex.message)
  if not task_template:
    raise TemplateNotFound('task template is not configured')

  build.swarming_hostname = swarming_cfg.hostname or settings.default_hostname
  if not build.swarming_hostname:  # pragma: no cover
    raise Error('default swarming hostname is not configured')
  task_template_params = {
    'bucket': build.bucket,
    'builder_hash': (
        hashlib.sha256('%s:%s' % (build.bucket, builder_cfg.name)).hexdigest()),
    'build_id': build.key.id(),
    'build_result_filename': BUILD_RUN_RESULT_FILENAME,
    'builder': builder_cfg.name,
    'cache_dir': CACHE_DIR,
    'hostname': app_identity.get_default_version_hostname(),
    'project': project_id,
    'swarming_hostname': build.swarming_hostname,
  }

  is_recipe = builder_cfg.HasField('recipe')
  if is_recipe:  # pragma: no branch
    build_properties = swarmingcfg_module.read_properties(builder_cfg.recipe)
    recipe_revision = builder_cfg.recipe.revision or 'HEAD'

    build_properties.update(
        buildername=builder_cfg.name,
        buildbucket=_buildbucket_property(build),
    )
    if build_number is not None:  # pragma: no branch
      build_properties['buildnumber'] = build_number

    changes = params.get(PARAM_CHANGES)
    if changes:  # pragma: no branch
      # Buildbucket-Buildbot integration passes repo_url of the first change in
      # build parameter "changes" as "repository" attribute of SourceStamp.
      # https://chromium.googlesource.com/chromium/tools/build/+/2c6023d
      # /scripts/master/buildbucket/changestore.py#140
      # Buildbot passes repository of the build source stamp as "repository"
      # build property. Recipes, in partiular bot_update recipe module, rely on
      # "repository" property and it is an almost sane property to support in
      # swarmbucket.
      repo_url = changes[0].get('repo_url')
      if repo_url:  # pragma: no branch
        build_properties['repository'] = repo_url

      # Buildbot-Buildbucket integration converts emails in changes to blamelist
      # property.
      emails = [c.get('author', {}).get('email') for c in changes]
      build_properties['blamelist'] = filter(None, emails)

    # Properties specified in build parameters must override any values derived
    # by swarmbucket.
    build_properties.update(build.parameters.get(PARAM_PROPERTIES) or {})

    task_template_params.update({
      'repository': builder_cfg.recipe.repository,
      'revision': recipe_revision,
      'recipe': builder_cfg.recipe.name,
      'properties_json': json.dumps(build_properties, sort_keys=True),
    })

  # Render task template.
  task_template_params = {
    k: v or '' for k, v in task_template_params.iteritems()}
  task = format_obj(task_template, task_template_params)

  if builder_cfg.priority > 0:  # pragma: no branch
    # Swarming accepts priority as a string
    task['priority'] = str(builder_cfg.priority)

  if builder_cfg.service_account:  # pragma: no branch
    # Don't pass it if not defined, for backward compatibility.
    task['service_account'] = builder_cfg.service_account

  swarming_tags = task.setdefault('tags', [])
  _extend_unique(swarming_tags, [
    'buildbucket_hostname:%s' % app_identity.get_default_version_hostname(),
    'buildbucket_bucket:%s' % build.bucket,
    'buildbucket_build_id:%s' % build.key.id(),
    'buildbucket_template_revision:%s' % task_template_rev,
  ])
  if is_recipe:  # pragma: no branch
    _extend_unique(swarming_tags, [
      'recipe_repository:%s' % builder_cfg.recipe.repository,
      'recipe_revision:%s' % recipe_revision,
      'recipe_name:%s' % builder_cfg.recipe.name,
    ])
  _extend_unique(swarming_tags, builder_cfg.swarming_tags)
  _extend_unique(swarming_tags, build.tags)
  swarming_tags.sort()

  task_properties = task.setdefault('properties', {})
  task_properties['dimensions'] = _to_swarming_dimensions(
      swarmingcfg_module.merge_dimensions(
          builder_cfg.dimensions,
          task_properties.get('dimensions', []),
      ))

  _add_named_caches(builder_cfg, task_properties)

  if builder_cfg.execution_timeout_secs > 0:
    task_properties['execution_timeout_secs'] = str(
        builder_cfg.execution_timeout_secs)

  if not fake_build:  # pragma: no branch | covered by swarmbucketapi_test.py
    task['pubsub_topic'] = (
      'projects/%s/topics/%s' %
      (app_identity.get_application_id(), PUBSUB_TOPIC))
    task['pubsub_userdata'] = json.dumps({
      'build_id': build.key.id(),
      'created_ts': utils.datetime_to_timestamp(utils.utcnow()),
      'swarming_hostname': build.swarming_hostname,
    }, sort_keys=True)
  raise ndb.Return(task)


def _to_swarming_dimensions(dims):
  """Converts dimensions from buildbucket format to swarming format."""
  return [
    {'key': key, 'value': value}
    for key, value in
    (s.split(':', 1) for s in dims)
  ]


def _add_named_caches(builder_cfg, task_properties):
  """Adds/replaces named caches to/in the task properties.

  Assumes builder_cfg is valid.
  """
  template_caches = task_properties.get('caches', [])
  task_properties['caches'] = []

  names = set()
  paths = set()
  for c in builder_cfg.caches:
    if c.path.startswith('cache/'):  # pragma: no cover
      # TODO(nodir): remove this code path onces clients remove "cache/" from
      # their configs.
      cache_path = c.path
    else:
      cache_path = posixpath.join(CACHE_DIR, c.path)
    names.add(c.name)
    paths.add(cache_path)
    task_properties['caches'].append({'path': cache_path, 'name': c.name, })

  for c in template_caches:
    if c.get('path') not in paths and c.get('name') not in names:
      task_properties['caches'].append(c)

  task_properties['caches'].sort(key=lambda p: p.get('path'))


@ndb.tasklet
def prepare_task_def_async(build, settings, fake_build=False):
  """Prepares a swarming task definition.

  Validates the new build.
  If configured, generates a build number and updates the build.
  Creates a swarming task definition.

  Sets build.swarming_hostname and build.canary attributes.
  May add "build_address" tag.

  Returns a task_def dict.
  """
  if build.lease_key:
    raise errors.InvalidInputError(
        'Swarming buckets do not support creation of leased builds')
  if not build.parameters:
    raise errors.InvalidInputError(
        'A build for bucket %r must have parameters' % build.bucket)
  builder_name = build.parameters.get(BUILDER_PARAMETER)
  if not isinstance(builder_name, basestring):
    raise errors.InvalidInputError('Invalid builder name %r' % builder_name)
  project_id, bucket_cfg = yield config.get_bucket_async(build.bucket)

  if not config.is_swarming_config(bucket_cfg):
    raise errors.InvalidInputError(
        'Bucket %s is not configured for swarming' % build.bucket)

  builder_cfg = None
  for b in bucket_cfg.swarming.builders:  # pragma: no branch
    if b.name == builder_name:  # pragma: no branch
      builder_cfg = b
      break
  if not builder_cfg:
    raise errors.InvalidInputError(
        'Builder %r is not defined in bucket %r' % (builder_name, build.bucket))

  build_number = None
  if builder_cfg.build_numbers:  # pragma: no branch
    seq_name = '%s/%s' % (build.bucket, builder_name)
    if fake_build:  # pragma: no cover | covered by swarmbucket_api_test
      build_number = 0
    else:
      build_number = yield sequence.generate_async(seq_name, 1)
    build.tags.append('build_address:%s/%d' % (seq_name, build_number))

  task_def = yield _create_task_def_async(
      project_id, bucket_cfg.swarming, builder_cfg, build, build_number,
      settings, fake_build)
  raise ndb.Return(task_def)


@ndb.tasklet
def create_task_async(build):
  """Creates a swarming task for the build and mutates the build.

  May be called only if build's bucket is configured for swarming.

  Raises:
    errors.InvalidInputError if build attribute values are inavlid.
  """
  settings = yield get_settings_async()
  task_def = yield prepare_task_def_async(build, settings)

  assert build.swarming_hostname
  res = yield _call_api_async(
      auth.get_current_identity(),
      build.swarming_hostname,
      'tasks/new',
      method='POST',
      payload=task_def,
      # Higher timeout than normal because if the task creation request
      # fails, but the task is actually created, later we will receive a
      # notification that the task is completed, but we won't have a build
      # for that task, which results in errors in the log.
      deadline=30,
      # This code path is executed by put and put_batch request handlers.
      # Clients should retry these requests on transient errors, so
      # do not retry requests to swarming.
      max_attempts=1)
  task_id = res['task_id']
  logging.info('Created a swarming task %s: %r', task_id, res)

  build.swarming_task_id = task_id

  build.tags.extend([
    'swarming_hostname:%s' % build.swarming_hostname,
    'swarming_task_id:%s' % task_id,
  ])
  task_req = res.get('request', {})
  for t in task_req.get('tags', []):
    build.tags.append('swarming_tag:%s' % t)
  for d in task_req.get('properties', {}).get('dimensions', []):
    build.tags.append('swarming_dimension:%s:%s' % (d['key'], d['value']))

  # Mark the build as leased.
  assert 'expiration_secs' in task_def, task_def
  # task['expiration_secs'] is max time for the task to be pending
  # It is encoded as string.
  task_expiration = datetime.timedelta(seconds=int(task_def['expiration_secs']))
  # task['execution_timeout_secs'] is max time for the task to run
  # It is encoded as string.
  task_expiration += datetime.timedelta(
      seconds=int(task_def['properties']['execution_timeout_secs']))
  task_expiration += datetime.timedelta(hours=1)
  build.lease_expiration_date = utils.utcnow() + task_expiration
  build.regenerate_lease_key()
  build.leasee = _self_identity()
  build.never_leased = False

  if settings.milo_hostname:
    build.url = (
        'https://%s/swarming/task/%s?server=%s' %
        (settings.milo_hostname, build.swarming_task_id,
         build.swarming_hostname))
  else:
    build.url = (
        'https://%s/task?id=%s' %
        (build.swarming_hostname, build.swarming_task_id))


def cancel_task_async(hostname, task_id):
  """Cancels a swarming task."""
  return _call_api_async(
      None, hostname, 'task/%s/cancel' % task_id, method='POST')


def cancel_task(hostname, task_id):
  """Sync version of cancel_task_async."""
  return cancel_task_async(hostname, task_id).get_result()


################################################################################
# Update builds.


def _load_task_result_async(
    impersonated_identity, hostname, task_id):  # pragma: no cover
  return _call_api_async(
      impersonated_identity, hostname, 'task/%s/result' % task_id)


@ndb.tasklet
def _load_build_run_result_async(task_result):
  """Fetches BUILD_RUN_RESULT_FILENAME from swarming task output."""
  outputs_ref = task_result.get('outputs_ref')
  if not outputs_ref:
    raise ndb.Return(None)

  server_prefix = 'https://'
  if not outputs_ref['isolatedserver'].startswith(server_prefix):
    raise BuildResultFileCorruptedError(
        'Bad isolatedserver %r read from task %s' %
        (outputs_ref['isolatedserver'], task_result['id']))

  hostname = outputs_ref['isolatedserver'][len(server_prefix):]

  @ndb.tasklet
  def fetch_json_async(loc):
    try:
      raw = yield isolate.fetch_async(loc)
      raise ndb.Return(json.loads(raw))
    except ValueError as ex:
      raise BuildResultFileCorruptedError(
          'could not load %s: %s' % (isolated_loc.human_url, ex))

  isolated_loc = isolate.Location(
      hostname, outputs_ref['namespace'], outputs_ref['isolated'])
  isolated = yield fetch_json_async(isolated_loc)

  # Assume the isolated file format
  result_entry = isolated['files'].get(BUILD_RUN_RESULT_FILENAME)
  if not result_entry:
    raise ndb.Return(None)

  result_loc = isolated_loc._replace(digest=result_entry['h'])
  build_result = yield fetch_json_async(result_loc)
  raise ndb.Return(build_result)


def _sync_build_in_memory(
    build, task_result, build_run_result, build_run_result_corrupted):
  """Syncs buildbucket |build| state with swarming task |result|."""
  # Task result docs:
  # https://github.com/luci/luci-py/blob/985821e9f13da2c93cb149d9e1159c68c72d58da/appengine/swarming/server/task_result.py#L239
  #
  # build_run_result is dict parsed from BuildRunResult JSONPB. May be None.
  # https://chromium.googlesource.com/infra/infra/+/924a4fa83c1c1018635544e5783f18eeb2ea2edc/go/src/infra/tools/kitchen/proto/result.proto

  if build.status == model.BuildStatus.COMPLETED:  # pragma: no cover
    # Completed builds are immutable.
    return False

  now = utils.utcnow()

  old_status = build.status
  build.status = None
  build.result = None
  build.failure_reason = None
  build.cancelation_reason = None
  # error message to include in result_details. Used only if build is complete.
  errmsg = ''

  terminal_states = (
    'EXPIRED',
    'TIMED_OUT',
    'BOT_DIED',
    'CANCELED',
    'COMPLETED',
  )
  state = (task_result or {}).get('state')
  if build_run_result_corrupted:
    build.status = model.BuildStatus.COMPLETED
    build.result = model.BuildResult.FAILURE
    build.failure_reason = model.FailureReason.INFRA_FAILURE
    errmsg = 'build_run_result.json returned by the swarming task is corrupted.'
  elif state is None:
    build.status = model.BuildStatus.COMPLETED
    build.result = model.BuildResult.FAILURE
    build.failure_reason = model.FailureReason.INFRA_FAILURE
    errmsg = (
        'Swarming task %s on %s unexpectedly disappeared' %
        (build.swarming_task_id, build.swarming_hostname))
  elif state == 'PENDING':
    build.status = model.BuildStatus.SCHEDULED
  elif state == 'RUNNING':
    build.status = model.BuildStatus.STARTED
  elif state in terminal_states:
    build.status = model.BuildStatus.COMPLETED
    if state == 'CANCELED':
      build.result = model.BuildResult.CANCELED
      build.cancelation_reason = model.CancelationReason.CANCELED_EXPLICITLY
    elif state == 'EXPIRED':
      # Task did not start.
      build.result = model.BuildResult.CANCELED
      build.cancelation_reason = model.CancelationReason.TIMEOUT
    elif state == 'TIMED_OUT':
      # Task started, but timed out.
      build.result = model.BuildResult.FAILURE
      build.failure_reason = model.FailureReason.INFRA_FAILURE
    elif state == 'BOT_DIED' or task_result.get('internal_failure'):
      build.result = model.BuildResult.FAILURE
      build.failure_reason = model.FailureReason.INFRA_FAILURE
    elif task_result.get('failure'):
      build.result = model.BuildResult.FAILURE
      if build_run_result and build_run_result.get('infra_failure'):
        build.failure_reason = model.FailureReason.INFRA_FAILURE
      else:
        build.failure_reason = model.FailureReason.BUILD_FAILURE
    else:
      assert state == 'COMPLETED'
      build.result = model.BuildResult.SUCCESS
  else:  # pragma: no cover
    assert False, 'Unexpected task state: %s' % state

  if build.status == old_status:  # pragma: no cover
    return False

  logging.info(
      'Build %s status: %s -> %s', build.key.id(), old_status, build.status)
  build.status_changed_time = now
  if build.status == model.BuildStatus.STARTED:
    build.start_time = now
  elif build.status == model.BuildStatus.COMPLETED:  # pragma: no branch
    logging.info('Build %s result: %s', build.key.id(), build.result)
    build.clear_lease()
    build.complete_time = now
    build.result_details = {
      'swarming': {
        'task_result': task_result,
      },
      'build_run_result': build_run_result,
    }
    if errmsg:
      build.result_details['error'] = {'message': errmsg}
  return True


@ndb.tasklet
def _sync_build_async(build_id, task_result, build_run_result):
  """Syncs Build entity in the datastore with the swarming task.

  Tries to load |build_run_result| from isolate if it is None.
  """
  build_run_result_corrupted = False
  if not build_run_result and task_result:
    try:
      build_run_result = yield _load_build_run_result_async(task_result)
    except BuildResultFileCorruptedError:
      logging.exception('build_run_result is corrupted')
      build_run_result_corrupted = True

  @ndb.transactional_tasklet
  def txn_async():
    build = yield model.Build.get_by_id_async(build_id)
    if not build:  # pragma: no cover
      raise ndb.Return(None)
    made_change = _sync_build_in_memory(
        build, task_result, build_run_result, build_run_result_corrupted)
    if not made_change:
      raise ndb.Return(None)

    futures = [build.put_async()]

    if build.status == model.BuildStatus.STARTED:
      futures.append(events.on_build_starting_async(build))
    elif build.status == model.BuildStatus.COMPLETED:  # pragma: no branch
      futures.append(events.on_build_completing_async(build))

    yield futures
    raise ndb.Return(build)

  build = yield txn_async()
  if build:
    if build.status == model.BuildStatus.STARTED:
      events.on_build_started(build)
    elif build.status == model.BuildStatus.COMPLETED:  # pragma: no branch
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
    msg = (self.request.json or {}).get('message', {})
    logging.info('Received message: %r', msg)

    hostname, created_time, task_id, build_id = self.unpack_msg(msg)
    task_url = 'https://%s/task?id=%s' % (hostname, task_id)

    # Load build.
    logging.info('Build id: %s', build_id)
    build = model.Build.get_by_id(build_id)
    if not build:
      if utils.utcnow() < created_time + datetime.timedelta(minutes=1):
        self.stop(
            'Build for a swarming task not found yet\nBuild: %s\nTask: %s',
            build_id, task_url, redeliver=True)
      self.stop(
          'Build for a swarming task not found\nBuild: %s\nTask: %s',
          build_id, task_url)

    # Ensure the loaded build is associated with the task.
    if build.swarming_hostname != hostname:
      self.stop(
          'swarming_hostname %s of build %s does not match %s',
          build.swarming_hostname, build_id, hostname)
    if build.swarming_task_id != task_id:
      self.stop(
          'swarming_task_id %s of build %s does not match %s',
          build.swarming_task_id, build_id, task_id)
    assert build.parameters

    # Update build.
    result = _load_task_result_async(None, hostname, task_id).get_result()
    _sync_build_async(build_id, result, None).get_result()

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
    self.abort(500 if redeliver else 200)

  def parse_json_obj(self, text, name):
    """Parses a JSON object from |text| if possible. Otherwise stops."""
    try:
      result = json.loads(text or '')
      if not isinstance(result, dict):
        raise ValueError()
      return result
    except ValueError:
      self.stop('%s is not a valid JSON object: %r', name, text)


class CronUpdateBuilds(webapp2.RequestHandler):
  """Updates builds that are associated with swarming tasks."""

  @ndb.tasklet
  def update_build_async(self, build):
    result = yield _load_task_result_async(
        None, build.swarming_hostname, build.swarming_task_id)
    if not result:
      logging.error(
          'Task %s/%s referenced by build %s is not found',
          build.swarming_hostname, build.swarming_task_id, build.key.id())
    yield _sync_build_async(build.key.id(), result, None)

  @decorators.require_cronjob
  def get(self):  # pragma: no cover
    q = model.Build.query(
        model.Build.swarming_task_id != None,
        # We cannot have a second negation filter, so use IN.
        # This will result in two datastore queries, which is fine.
        model.Build.status.IN(
            [model.BuildStatus.SCHEDULED, model.BuildStatus.STARTED]))
    q.map_async(self.update_build_async).get_result()


def get_backend_routes():  # pragma: no cover
  return [
    webapp2.Route(
        r'/internal/cron/swarming/update_builds',
        CronUpdateBuilds),
    webapp2.Route(
        r'/_ah/push-handlers/swarming/notify',
        SubNotify),
  ]


################################################################################
# Utility functions


@ndb.tasklet
def _call_api_async(
    impersonated_identity, hostname, path, method='GET', payload=None,
    deadline=None, max_attempts=None):
  """Calls Swarming API.

  If impersonated_identity is None, does not impersonate.
  """
  delegation_token = None
  if impersonated_identity:
    delegation_token = yield auth.delegate_async(
        audience=[_self_identity()],
        services=['https://%s' % hostname],
        impersonate=impersonated_identity,
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


@utils.cache
def _self_identity():
  return auth.Identity('user', app_identity.get_service_account_name())


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


def _extend_unique(target, items):
  for x in items:
    if x not in target:  # pragma: no branch
      target.append(x)
