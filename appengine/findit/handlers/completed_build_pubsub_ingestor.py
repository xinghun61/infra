# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This serves as a handler for PubSub push for builds."""

import base64
import json
import logging
import re
import urlparse

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.protobuf import json_format
from google.protobuf.field_mask_pb2 import FieldMask

from gae_libs import appengine_util
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission

from common import constants
from common.waterfall.buildbucket_client import GetV2Build
from model.isolated_target import IsolatedTarget

_PROP_NAME_REGEX = re.compile(
    r'swarm_hashes_(?P<ref>.*)\(at\)\{\#(?P<cp>[0-9]+)\}'
    r'(?P<suffix>(_with(out)?_patch))?')

# Builds from such LUCI projects should be intercepted by Findit v2.
# It doesn't necessarily mean build failures will be analyzed in v2 though.
_FINDIT_V2_INTERCEPT_PROJECTS = ['chromium', 'chromeos']


class CompletedBuildPubsubIngestor(BaseHandler):
  """Adds isolate targets to the index when pubsub notifies of completed build.
  """

  PERMISSION_LEVEL = Permission.ANYONE  # Protected with login:admin.

  def HandlePost(self):
    build_id = None
    build_result = None
    status = None
    project = None
    bucket = None
    builder_name = None
    try:
      envelope = json.loads(self.request.body)
      version = envelope['message']['attributes'].get('version')
      if version and version != 'v1':
        logging.info('Ignoring versions other than v1')
        return
      build_id = envelope['message']['attributes']['build_id']
      build = json.loads(base64.b64decode(envelope['message']['data']))['build']
      build_result = build.get('result')
      status = build['status']
      project = build['project']
      bucket = build['bucket']
      parameters_json = json.loads(build['parameters_json'])
      builder_name = parameters_json['builder_name']
    except (ValueError, KeyError) as e:
      # Ignore requests with invalid message.
      logging.debug('build_id: %r', build_id)
      logging.error('Unexpected PubSub message format: %s', e.message)
      logging.debug('Post body: %s', self.request.body)
      return

    if status == 'COMPLETED':
      _HandlePossibleCodeCoverageBuild(int(build_id))
      if project in _FINDIT_V2_INTERCEPT_PROJECTS:
        _HandlePossibleFailuresInBuild(project, bucket, builder_name,
                                       int(build_id), build_result)
        if project == 'chromium':
          # Only ingests chromium builds.

          # TODO (crbug.com/966982): Remove when v2 for chromium is working.
          _TriggerV1AnalysisForChromiumBuildIfNeeded(bucket, builder_name,
                                                     int(build_id),
                                                     build_result)
          return _IngestProto(int(build_id))
    # We don't care about pending or non-supported builds, so we accept the
    # notification by returning 200, and prevent pubsub from retrying it.


def _HandlePossibleCodeCoverageBuild(build_id):  # pragma: no cover
  """Schedules a taskqueue task to process the code coverage data."""
  # https://cloud.google.com/appengine/docs/standard/python/taskqueue/push/creating-tasks#target
  try:
    taskqueue.add(
        name='coveragedata-%s' % build_id,  # Avoid duplicate tasks.
        url='/coverage/task/process-data/build/%s' % build_id,
        target='code-coverage-backend',  # Always use the default version.
        queue_name='code-coverage-process-data')
  except (taskqueue.TombstonedTaskError, taskqueue.TaskAlreadyExistsError):
    logging.warning('Build %s was already scheduled to be processed', build_id)


def _HandlePossibleFailuresInBuild(project, bucket, builder_name, build_id,
                                   build_result):  # pragma: no cover
  """Schedules a taskqueue task to process a completed failed build."""
  try:
    taskqueue.add(
        name='buildfailure-%s' % build_id,  # Avoid duplicate tasks.
        url='/findit/internal/v2/task/build-completed',
        payload=json.dumps({
            'project': project,
            'bucket': bucket,
            'builder_name': builder_name,
            'build_id': build_id,
            'build_result': build_result,
        }),
        target=appengine_util.GetTargetNameForModule('findit-backend'),
        queue_name='failure-detection-queue')
  except (taskqueue.TombstonedTaskError, taskqueue.TaskAlreadyExistsError):
    logging.warning('Build %s was already scheduled to be processed', build_id)


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

  commit = build.input.gitiles_commit
  patches = build.input.gerrit_changes

  # Convert the Struct to standard dict, to use .get, .iteritems etc.
  properties = json_format.MessageToDict(build.output.properties)

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
              commit_position=commit_position,
              revision=properties.get('got_revision')))
  result = [key.pairs() for key in ndb.put_multi(entities)]
  return {'data': {'created_rows': result}}


def _TriggerV1AnalysisForChromiumBuildIfNeeded(bucket, builder_name, build_id,
                                               build_result):
  """Temporary solution of triggering v1 analysis until v2 is ready."""
  if 'ci' not in bucket:
    return

  if build_result != 'FAILURE':
    logging.debug('Build %d is not a failure', build_id)
    return

  assert build_id
  build = GetV2Build(
      build_id, fields=FieldMask(paths=['id', 'number', 'output.properties']))

  # Sanity check.
  assert build, 'Failed to download build for {}.'.format(build_id)
  assert build_id == build.id, (
      'Build id {} is different from the requested id {}.'.format(
          build.id, build_id))
  assert build.number, 'No build_number for chromium build {}'.format(build_id)

  # Converts the Struct to standard dict, to use .get, .iteritems etc.
  properties = json_format.MessageToDict(build.output.properties)
  master_name = properties.get('target_mastername',
                               properties.get('mastername'))
  if not master_name:
    logging.error('Build %d does not have expected "mastername" property',
                  build_id)
    return

  build_info = {
      'master_name': master_name,
      'builder_name': builder_name,
      'build_number': build.number,
  }

  logging.info('Triggering v1 analysis for chromium build %d', build_id)
  target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
  payload = json.dumps({'builds': [build_info]})
  taskqueue.add(
      url=constants.WATERFALL_PROCESS_FAILURE_ANALYSIS_REQUESTS_URL,
      payload=payload,
      target=target,
      queue_name=constants.WATERFALL_FAILURE_ANALYSIS_REQUEST_QUEUE)
