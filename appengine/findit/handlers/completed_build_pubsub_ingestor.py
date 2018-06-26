# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This serves as a handler for PubSub push for builds."""

import base64
import json
import logging
import re
import urlparse

from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask

from buildbucket_proto.build_pb2 import Build
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission

from common.waterfall.buildbucket_client import GetV2Build
from model.isolated_target import IsolatedTarget

_PROP_NAME_REGEX = re.compile(
    r'swarm_hashes_(?P<ref>.*)\(at\)\{\#(?P<cp>[0-9]+)\}'
    r'(?P<suffix>(_with(out)?_patch))?')


class CompletedBuildPubsubIngestor(BaseHandler):
  """Adds isolate targets to the index when pubsub notifies of completed build.
  """

  PERMISSION_LEVEL = Permission.ANYONE  # Protected with login:admin.

  def HandlePost(self):
    logging.debug('Post body: %s', self.request.body)
    try:
      envelope = json.loads(self.request.body)
      build_id = envelope['message']['attributes']['build_id']
      version = envelope['message']['attributes'].get('version')
      if version and version != 'v1':
        logging.info('Ignoring versions other than v1')
        return
      build = json.loads(base64.b64decode(envelope['message']['data']))['build']
    except (ValueError, KeyError) as e:
      # Ignore requests with invalid message.
      logging.warning('Unexpected PubSub message format: %s', e.message)
      return

    if build['status'] == 'COMPLETED' and build['project'] == 'chromium':
      return _IngestProto(int(build_id))
    # We don't care about pending or non-chromium builds, so we accept the
    # notification by returning 200, and prevent pubsub from retrying it.


def _DecodeSwarmingHashesPropertyName(prop):
  """Extracts ref, commit position and patch status from property name.

  Args:
    prop(str): The property name is expected to be in the following format:
  swarm_hashes_<ref>(at){#<commit_position}<optional suffix>
  """
  matches = _PROP_NAME_REGEX.match(prop)
  with_patch = matches.group('suffix') == '_with_patch'
  return matches.group('ref'), int(matches.group('cp')), with_patch


def _IngestProto(build_id):
  """Process a build described in a proto, i.e. buildbucket v2 api format."""
  assert build_id
  build = GetV2Build(
      build_id,
      fields=FieldMask(
          paths=['id', 'output.properties', 'input', 'status', 'builder']))

  if not build:
    return BaseHandler.CreateError(
        'Could not retrieve build #%d from buildbucket, retry' % build_id, 404)

  # Sanity check.
  assert build_id == build.id

  properties_struct = build.output.properties
  commit = build.input.gitiles_commit
  patches = build.input.gerrit_changes

  # Convert the Struct to standard dict, to use .get, .iteritems etc.
  properties = dict(properties_struct.items())

  swarm_hashes_properties = {}
  for k, v in properties.iteritems():
    if _PROP_NAME_REGEX.match(k):
      swarm_hashes_properties[k] = v

  if not swarm_hashes_properties:
    logging.debug('Build %d does not have swarm_hashes property', build_id)
    return

  master_name = properties.get('target_mastername',
                               properties.get('mastername'))
  if not master_name:
    logging.error('Build %d does not have expected "mastername" property',
                  build_id)
    return

  luci_project = build.builder.project
  luci_bucket = build.builder.bucket
  luci_builder = properties.get('target_buildername') or build.builder.builder

  if commit.host:
    gitiles_host = commit.host
    gitiles_project = commit.project
    gitiles_ref = commit.ref or 'refs/heads/master'
  else:
    # Non-ci build, use 'repository' property instead to get base revision
    # information.
    repo_url = urlparse.urlparse(properties.get('repository', ''))
    gitiles_host = repo_url.hostname or ''
    gitiles_project = repo_url.path or ''

    # Trim "/" prefix so that "/chromium/src" becomes
    # "chromium/src", also remove ".git" suffix if present.
    if gitiles_project.startswith('/'):  # pragma: no branch
      gitiles_project = gitiles_project[1:]
    if gitiles_project.endswith('.git'):  # pragma: no branch
      gitiles_project = gitiles_project[:-len('.git')]
    gitiles_ref = properties.get('gitiles_ref', 'refs/heads/master')

  gerrit_patch = None
  if len(patches) > 0:
    gerrit_patch = '/'.join(
        map(str, [patches[0].host, patches[0].change, patches[0].patchset]))

  entities = []
  for prop_name, swarm_hashes in swarm_hashes_properties.iteritems():
    ref, commit_position, with_patch = _DecodeSwarmingHashesPropertyName(
        prop_name)
    for target_name, isolated_hash in swarm_hashes.items():
      entities.append(
          IsolatedTarget.Create(
              build_id=build_id,
              luci_project=luci_project,
              bucket=luci_bucket,
              master_name=master_name,
              builder_name=luci_builder,
              gitiles_host=gitiles_host,
              gitiles_project=gitiles_project,
              gitiles_ref=gitiles_ref or ref,
              gerrit_patch=gerrit_patch if with_patch else '',
              target_name=target_name,
              isolated_hash=isolated_hash,
              commit_position=commit_position))
  result = [key.pairs() for key in ndb.put_multi(entities)]
  return {'data': {'created_rows': result}}
