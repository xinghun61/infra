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

from proto import project_config_pb2
import errors


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


def get_buckets():
  """Returns a list of project_config_pb2.Bucket objects."""
  buckets = Bucket.query().fetch()
  return [parse_bucket_config(b.config_content) for b in buckets]


def get_bucket(name):
  """Returns a project_config_pb2.Bucket by name."""
  bucket = Bucket.get_by_id(name)
  if bucket is None:
    return None
  return parse_bucket_config(bucket.config_content)


def cron_update_buckets():
  """Synchronizes Bucket entities with configs fetched from luci-config."""
  config_name = '%s.cfg' % app_identity.get_application_id()
  config_map = config.get_project_configs(
      config_name, project_config_pb2.BuildbucketCfg)

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
