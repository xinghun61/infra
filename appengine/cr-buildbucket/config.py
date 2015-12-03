# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Access to bucket configurations.

Stores bucket list in datastore, synchronizes it with bucket configs in
project repositories: `projects/<project_id>:<buildbucket-app-id>.cfg`.
"""

import hashlib
import logging

from google import protobuf
from google.appengine.api import app_identity
from google.appengine.ext import ndb

from components import auth
from components import config
from components import utils
from components.config import validation
from proto import project_config_pb2
import errors


@utils.cache
def cfg_path():
  try:
    appid = app_identity.get_application_id()
  except AttributeError:
    # Raised in testbed environment because cfg_path is called
    # during decoration.
    appid = 'buildbucket'
  return '%s.cfg' % appid


def validate_identity(identity, ctx):
  if ':' in identity:
    kind, name = identity.split(':', 2)
  else:
    kind = 'user'
    name = identity
  try:
    auth.Identity(kind, name)
  except ValueError as ex:
    ctx.error(ex)


def validate_swarming_tag(tag, ctx):
  # a valid swarming tag is a string that contains ":"
  if ':' not in tag:
    ctx.error('does not have ":": %s', tag)


def validate_swarming_builder(builder, ctx):
  if not builder.name:
    ctx.error('name unspecified')
  for i, t in enumerate(builder.swarming_tags):
    with ctx.prefix('tag #%d: ', i + 1):
      validate_swarming_tag(t, ctx)

  if not builder.HasField('recipe'):
    ctx.error('recipe unspecified')
  elif not builder.recipe.name:
    ctx.error('recipe name unspecified')
  if builder.priority < 0 or builder.priority > 200:
    ctx.error('priority must be in [0, 200] range; got %d', builder.priority)


def validate_swarming(swarming, ctx):
  if not swarming.hostname:
    ctx.error('hostname unspecified')
  for i, t in enumerate(swarming.common_swarming_tags):
    with ctx.prefix('common tag #%d: ', i + 1):
      validate_swarming_tag(t, ctx)
  for i, b in enumerate(swarming.builders):
    with ctx.prefix('builder %s: ' % (b.name or '#%s' % (i + 1))):
      validate_swarming_builder(b, ctx)


@validation.project_config_rule(cfg_path(), project_config_pb2.BuildbucketCfg)
def validate_buildbucket_cfg(cfg, ctx):
  is_sorted = True
  bucket_names = set()

  for i, bucket in enumerate(cfg.buckets):
    with ctx.prefix('Bucket %s: ', bucket.name or ('#%d' % (i + 1))):
      try:
        errors.validate_bucket_name(bucket.name)
      except errors.InvalidInputError as ex:
        ctx.error('invalid name: %s', ex.message)
      else:
        if bucket.name in bucket_names:
          ctx.error('duplicate bucket name')
        else:
          bucket_names.add(bucket.name)
          if ctx.project_id:  # pragma: no branch
            bucket_entity = Bucket.get_by_id(bucket.name)
            if bucket_entity and bucket_entity.project_id != ctx.project_id:
              ctx.error('this name is already reserved by another project')

        if is_sorted and i > 0 and cfg.buckets[i - 1].name:
          if bucket.name < cfg.buckets[i - 1].name:
            is_sorted = False

      for i, acl in enumerate(bucket.acls):
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
      if bucket.HasField('swarming'):
        with ctx.prefix('swarming: '):
          validate_swarming(bucket.swarming, ctx)
  if not is_sorted:
    ctx.warning('Buckets are not sorted by name')


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
  # Project id in luci-config.
  project_id = ndb.StringProperty(required=True)
  # Bucket revision matches its config revision.
  revision = ndb.StringProperty(required=True)
  # Bucket configuration (Bucket message in project_config.proto),
  # copied from luci-config for consistency and simplicity.
  # Stored in text format.
  config_content = ndb.TextProperty(required=True)


def parse_bucket_config(text):
  cfg = project_config_pb2.Bucket()
  protobuf.text_format.Merge(text, cfg)
  return cfg


@ndb.non_transactional
@ndb.tasklet
def get_buckets_async():
  """Returns a list of project_config_pb2.Bucket objects."""
  buckets = yield Bucket.query().fetch_async()
  raise ndb.Return([parse_bucket_config(b.config_content) for b in buckets])


@ndb.non_transactional
@ndb.tasklet
def get_bucket_async(name):
  """Returns a project_config_pb2.Bucket by name."""
  bucket = yield Bucket.get_by_id_async(name)
  if bucket is None:
    raise ndb.Return(None)
  raise ndb.Return(parse_bucket_config(bucket.config_content))


def cron_update_buckets():
  """Synchronizes Bucket entities with configs fetched from luci-config."""
  config_map = config.get_project_configs(
    cfg_path(), project_config_pb2.BuildbucketCfg)

  buckets_of_project = {
    pid: set(b.name for b in pcfg.buckets)
    for pid, (_, pcfg) in config_map.iteritems()
  }

  for project_id, (revision, project_cfg) in config_map.iteritems():
    # revision is None in file-system mode. Use SHA1 of the config as revision.
    revision = revision or 'sha1:%s' % hashlib.sha1(
      project_cfg.SerializeToString()).hexdigest()
    for bucket_cfg in project_cfg.buckets:
      bucket = Bucket.get_by_id(bucket_cfg.name)
      if (bucket and
          bucket.project_id == project_id and
          bucket.revision == revision):
        continue

      for acl in bucket_cfg.acls:
        if acl.identity and ':' not in acl.identity:
          acl.identity = 'user:%s' % acl.identity

      @ndb.transactional
      def update_bucket():
        bucket = Bucket.get_by_id(bucket_cfg.name)
        if bucket and bucket.project_id != project_id:
          # Does bucket.project_id still claim this bucket?
          if bucket_cfg.name in buckets_of_project.get(bucket.project_id, []):
            logging.error(
              'Failed to reserve bucket %s for project %s: '
              'already reserved by %s',
              bucket_cfg.name, project_id, bucket.project_id)
            return
        if (bucket and
            bucket.project_id == project_id and
            bucket.revision == revision):  # pragma: no coverage
          return

        report_reservation = bucket is None or bucket.project_id != project_id
        Bucket(
          id=bucket_cfg.name,
          project_id=project_id,
          revision=revision,
          config_content=protobuf.text_format.MessageToString(bucket_cfg),
        ).put()
        if report_reservation:
          logging.warning(
            'Reserved bucket %s for project %s', bucket_cfg.name, project_id)
        logging.info(
          'Updated bucket %s to revision %s', bucket_cfg.name, revision)

      update_bucket()

  # Delete/unreserve non-existing buckets.
  all_bucket_keys = Bucket.query().fetch(keys_only=True)
  existing_bucket_keys = [
    ndb.Key(Bucket, b)
    for buckets in buckets_of_project.itervalues()
    for b in buckets
  ]
  to_delete = set(all_bucket_keys).difference(existing_bucket_keys)
  if to_delete:
    logging.warning(
      'Deleting buckets: %s', ', '.join(k.id() for k in to_delete))
    ndb.delete_multi(to_delete)
