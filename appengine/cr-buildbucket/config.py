# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access to bucket configurations.

Stores bucket list in datastore, synchronizes it with bucket configs in
project repositories: `projects/<project_id>:<buildbucket-app-id>.cfg`.
"""

import collections
import hashlib
import logging
import re

from components import utils
utils.fix_protobuf_package()

from google import protobuf
from google.appengine.api import app_identity
from google.appengine.ext import ndb

from components import auth
from components import config
from components import gitiles
from components.config import validation

from proto.config import project_config_pb2
from proto.config import service_config_pb2
import errors

CURRENT_BUCKET_SCHEMA_VERSION = 4
ACL_SET_NAME_RE = re.compile('^[a-z0-9_]+$')


@utils.cache
def cfg_path():
  """Returns relative buildbucket config file path."""
  try:
    appid = app_identity.get_application_id()
  except AttributeError:  # pragma: no cover | does not get run on some bots
    # Raised in testbed environment because cfg_path is called
    # during decoration.
    appid = 'testbed-test'
  return '%s.cfg' % appid


@utils.cache
def self_config_set():
  """Returns buildbucket's service config set."""
  try:
    return config.self_config_set()
  except AttributeError:  # pragma: no cover | does not get run on some bots
    # Raised in testbed environment because cfg_path is called
    # during decoration.
    return 'services/testbed-test'


def validate_identity(identity, ctx):
  if ':' in identity:
    kind, name = identity.split(':', 2)
  else:
    kind = 'user'
    name = identity
  try:
    auth.Identity(kind, name)
  except ValueError as ex:
    ctx.error('%s', ex)


def validate_access_list(acl_list, ctx):
  """Validates a list of Acl messages."""
  for i, acl in enumerate(acl_list):
    with ctx.prefix('acl #%d: ', i + 1):
      if acl.group and acl.identity:
        ctx.error('either group or identity must be set, not both')
      elif acl.group:
        if not auth.is_valid_group_name(acl.group):
          ctx.error('invalid group: %s', acl.group)
      elif acl.identity:
        validate_identity(acl.identity, ctx)
      else:
        ctx.error('group or identity must be set')


@validation.project_config_rule(cfg_path(), project_config_pb2.BuildbucketCfg)
def validate_buildbucket_cfg(cfg, ctx):
  from swarming import swarmingcfg

  acl_set_names = set()
  for i, acl_set in enumerate(cfg.acl_sets):
    with ctx.prefix('ACL set #%d (%s): ', i + 1, acl_set.name):
      if not acl_set.name:
        ctx.error('name is unspecified')
      elif not ACL_SET_NAME_RE.match(acl_set.name):
        ctx.error(
            'invalid name "%s" does not match regex %r', acl_set.name,
            ACL_SET_NAME_RE.pattern
        )
      elif acl_set.name in acl_set_names:
        ctx.error('duplicate name "%s"', acl_set.name)
      acl_set_names.add(acl_set.name)

      validate_access_list(acl_set.acls, ctx)

  mixin_ctx = validation.Context(  # pragma: no cover
      on_message=lambda msg: ctx.msg(msg.severity, '%s', msg.text))
  swarmingcfg.validate_builder_mixins(cfg.builder_mixins, mixin_ctx)
  mixins_are_valid = not mixin_ctx.result().has_errors
  mixin_by_name = {m.name: m for m in cfg.builder_mixins}

  bucket_names = set()

  for i, bucket in enumerate(cfg.buckets):
    with ctx.prefix('Bucket %s: ', bucket.name or ('#%d' % (i + 1))):
      try:
        errors.validate_bucket_name(bucket.name, project_id=ctx.project_id)
      except errors.InvalidInputError as ex:
        ctx.error('invalid name: %s', ex.message)
      else:
        if bucket.name in bucket_names:
          ctx.error('duplicate bucket name')
        else:
          bucket_names.add(bucket.name)
          if i > 0 and bucket.name < cfg.buckets[i - 1].name:
            ctx.warning('out of order')

      validate_access_list(bucket.acls, ctx)
      for name in bucket.acl_sets:
        if name not in acl_set_names:
          ctx.error(
              'undefined ACL set "%s". '
              'It must be defined in the same file', name
          )

      if bucket.HasField('swarming'):  # pragma: no cover
        with ctx.prefix('swarming: '):
          swarmingcfg.validate_project_cfg(
              bucket.swarming, mixin_by_name, mixins_are_valid, ctx
          )


@validation.rule(
    self_config_set(), 'settings.cfg', service_config_pb2.SettingsCfg
)
def validate_settings_cfg(cfg, ctx):  # pragma: no cover
  from swarming import swarmingcfg

  if cfg.HasField('swarming'):
    with ctx.prefix('swarming: '):
      swarmingcfg.validate_service_cfg(cfg.swarming, ctx)


class Bucket(ndb.Model):
  """Stores project a bucket belongs to, and its ACLs.

  For historical reasons, some bucket names must match Chromium Buildbot master
  names, therefore they may not contain project id. Consequently, it is
  impossible to retrieve a project id from bucket name without an additional
  {bucket_name -> project_id} map. This entity kind is used to store the mapping
  and a copy of a bucket config retrieved from luci-config.

  By storing this mapping, we reserve bucket names for projects. If project X
  is trying to use a bucket name already being used by project Y, the
  config of projct X is considered invalid.

  Bucket entities are updated in cron_update_buckets() from project configs.

  Entity key:
    Root entity. Id is bucket name.
  """
  # Version of entity schema. If not current, cron_update_buckets will update
  # the entity forcefully.
  entity_schema_version = ndb.IntegerProperty()
  # Project id in luci-config.
  # TODO(crbug.com/851036): move project_id to the entity key.
  project_id = ndb.StringProperty(required=True)
  # Bucket revision matches its config revision.
  revision = ndb.StringProperty(required=True)
  # Bucket configuration (Bucket message in project_config.proto),
  # copied verbatim from luci-config for get_bucket API.
  # Must not be used in by serving code paths, use config_content_binary
  # instead.
  config_content = ndb.TextProperty(required=True)
  # Binary equivalent of config_content.
  config_content_binary = ndb.BlobProperty(required=True)


def parse_binary_bucket_config(cfg_bytes):
  cfg = project_config_pb2.Bucket()
  cfg.MergeFromString(cfg_bytes)
  return cfg


def is_swarming_config(cfg):
  """Returns True if this is a Swarming bucket config."""
  return cfg and cfg.HasField('swarming')


@ndb.non_transactional
@ndb.tasklet
def get_buckets_async(names=None):
  """Returns a list of configured buckets.

  If names is None, returns all buckets.
  Otherwise returns only specified buckets, in the same order as names.
  If a bucket doesn't exist, the corresponding element of the returned list
  will be None.

  Returns:
    List of (project_id, project_config_pb2.Bucket) tuples.
  """
  if names is None:
    buckets = yield Bucket.query().fetch_async()
  else:
    buckets = yield ndb.get_multi_async([ndb.Key(Bucket, n) for n in names])

  ret = []
  for b in buckets:
    ret.append((
        b.project_id,
        parse_binary_bucket_config(b.config_content_binary) if b else None,
    ))
  raise ndb.Return(ret)


@ndb.non_transactional
@ndb.tasklet
def get_bucket_async(name):
  """Returns a (project, project_config_pb2.Bucket) tuple."""
  bucket = yield Bucket.get_by_id_async(name)
  if bucket is None:
    raise ndb.Return(None, None)
  raise ndb.Return(
      bucket.project_id,
      parse_binary_bucket_config(bucket.config_content_binary)
  )


@ndb.non_transactional
def get_bucket(name):
  """Returns a (project, project_config_pb2.Bucket) tuple."""
  return get_bucket_async(name).get_result()


def _normalize_acls(acls):
  """Normalizes a RepeatedCompositeContainer of Acl messages."""
  for a in acls:
    if a.identity and ':' not in a.identity:
      a.identity = 'user:%s' % a.identity

  sort_key = lambda a: (a.role, a.group, a.identity)
  acls.sort(key=sort_key)

  for i in xrange(len(acls) - 1, 0, -1):
    if sort_key(acls[i]) == sort_key(acls[i - 1]):
      del acls[i]


def put_bucket(project_id, revision, bucket_cfg):
  Bucket(
      id=bucket_cfg.name,
      entity_schema_version=CURRENT_BUCKET_SCHEMA_VERSION,
      project_id=project_id,
      revision=revision,
      config_content=protobuf.text_format.MessageToString(bucket_cfg),
      config_content_binary=bucket_cfg.SerializeToString(),
  ).put()


def cron_update_buckets():
  """Synchronizes Bucket entities with configs fetched from luci-config.

  When storing in the datastore, inlines the referenced ACL sets and clears
  the acl_sets message field. Also inlines swarmbucket builder defaults and
  mixins and clears Builder.mixins field.
  """
  from swarming import flatten_swarmingcfg
  from swarming import swarmingcfg

  config_map = config.get_project_configs(
      cfg_path(), project_config_pb2.BuildbucketCfg
  )

  to_delete = collections.defaultdict(set)  # project_id -> set of bucket names
  for bucket in Bucket.query().fetch():
    # TODO(crbug.com/851036): use key only query when bucket id includes
    # project id
    to_delete[bucket.project_id].add(bucket.key.id())

  for project_id, (revision, project_cfg, _) in config_map.iteritems():
    if project_cfg is None:
      logging.error('config of project %s is broken', project_id)
      # Do not delete all buckets of a broken project.
      to_delete.pop(project_id, None)
      continue

    # revision is None in file-system mode. Use SHA1 of the config as revision.
    revision = revision or 'sha1:%s' % hashlib.sha1(
        project_cfg.SerializeToString()
    ).hexdigest()
    acl_sets_by_name = {a.name: a for a in project_cfg.acl_sets}
    builder_mixins_by_name = {m.name: m for m in project_cfg.builder_mixins}

    for bucket_cfg in project_cfg.buckets:
      to_delete[project_id].discard(bucket_cfg.name)
      bucket = Bucket.get_by_id(bucket_cfg.name)
      if (bucket and
          bucket.entity_schema_version == CURRENT_BUCKET_SCHEMA_VERSION and
          bucket.project_id == project_id and bucket.revision == revision and
          bucket.config_content_binary):
        continue

      # Inline ACL sets.
      for name in bucket_cfg.acl_sets:
        acl_set = acl_sets_by_name.get(name)
        if not acl_set:
          logging.error(
              'referenced acl_set not found.\n'
              'Bucket: %r\n'
              'ACL set name: %r\n'
              'Project id: %r\n'
              'Config revision: %r', bucket_cfg.name, name, project_id, revision
          )
          continue
        bucket_cfg.acls.extend(acl_set.acls)
      del bucket_cfg.acl_sets[:]

      _normalize_acls(bucket_cfg.acls)

      if bucket_cfg.HasField('swarming'):
        # Pull builder defaults out and apply default pool.
        defaults = bucket_cfg.swarming.builder_defaults
        bucket_cfg.swarming.ClearField('builder_defaults')
        if not any(d.startswith('pool:') for d in defaults.dimensions):
          # TODO(crbug.com/851036): make it "luci.<project>.<bucket name>".
          defaults.dimensions.append('pool:' + bucket_cfg.name)
        for b in bucket_cfg.swarming.builders:
          flatten_swarmingcfg.flatten_builder(
              b, defaults, builder_mixins_by_name
          )

      @ndb.transactional
      def update_bucket():
        bucket = Bucket.get_by_id(bucket_cfg.name)
        if (bucket and
            bucket.entity_schema_version == CURRENT_BUCKET_SCHEMA_VERSION and
            bucket.project_id == project_id and bucket.revision == revision and
            bucket.config_content_binary):  # pragma: no coverage
          return

        put_bucket(project_id, revision, bucket_cfg)
        logging.info(
            'Updated bucket %s to revision %s', bucket_cfg.name, revision
        )

      update_bucket()

  # Delete non-existing buckets.
  to_delete_flat = sum([list(n) for n in to_delete.itervalues()], [])
  if to_delete_flat:
    logging.warning('Deleting buckets: %s', ', '.join(to_delete_flat))
    ndb.delete_multi(ndb.Key(Bucket, n) for n in to_delete_flat)


def get_buildbucket_cfg_url(project_id):
  """Returns URL of a buildbucket config file in a project, or None."""
  config_url = config.get_config_set_location('projects/%s' % project_id)
  if config_url is None:  # pragma: no cover
    return None
  try:
    loc = gitiles.Location.parse(config_url)
  except ValueError:  # pragma: no cover
    logging.exception(
        'Not a valid Gitiles URL %r of project %s', config_url, project_id
    )
    return None
  return str(loc.join(cfg_path()))


@ndb.tasklet
def get_settings_async():  # pragma: no cover
  _, global_settings = yield config.get_self_config_async(
      'settings.cfg', service_config_pb2.SettingsCfg, store_last_good=True
  )
  raise ndb.Return(global_settings or service_config_pb2.SettingsCfg())
