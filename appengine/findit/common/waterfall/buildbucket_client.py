# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""""Serves as a client for selected APIs in Buildbucket."""

import collections
import json
import logging

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.build_pb2 import BuilderID
from buildbucket_proto.rpc_pb2 import BuildPredicate
from buildbucket_proto.rpc_pb2 import GetBuildRequest
from buildbucket_proto.rpc_pb2 import ScheduleBuildRequest
from buildbucket_proto.rpc_pb2 import SearchBuildsRequest
from buildbucket_proto.rpc_pb2 import SearchBuildsResponse
from common.findit_http_client import FinditHttpClient
from libs.math.integers import constrain

# https://github.com/grpc/grpc-go/blob/master/codes/codes.go
GRPC_OK = '0'

# TODO: save these settings in datastore and create a role account.
_BUILDBUCKET_HOST = 'cr-buildbucket.appspot.com'
_BUILDBUCKET_PUT_GET_ENDPOINT = (
    'https://{hostname}/_ah/api/buildbucket/v1/builds'.format(
        hostname=_BUILDBUCKET_HOST))
_LUCI_PREFIX = 'luci.'
_BUILDBUCKET_V2_GET_BUILD_ENDPOINT = (
    'https://{hostname}/prpc/buildbucket.v2.Builds/GetBuild'.format(
        hostname=_BUILDBUCKET_HOST))
_BUILDBUCKET_V2_SEARCH_BUILDS_ENDPOINT = (
    'https://{hostname}/prpc/buildbucket.v2.Builds/SearchBuilds'.format(
        hostname=_BUILDBUCKET_HOST))
_BUILDBUCKET_V2_SCHEDULE_BUILD_ENDPOINT = (
    'https://{hostname}/prpc/buildbucket.v2.Builds/ScheduleBuild'.format(
        hostname=_BUILDBUCKET_HOST))


def _GetBucketName(master_name):
  """Converts shortened master name to full master name.

  Buildbucket uses full master name (master.tryserver.chromium.linux) as bucket
  name, while Findit uses shortened master name (tryserver.chromium.linux).
  """
  buildbot_prefix = 'master.'
  if (master_name.startswith(buildbot_prefix) or
      master_name.startswith(_LUCI_PREFIX)):
    return master_name
  return '%s%s' % (buildbot_prefix, master_name)


class PubSubCallback(
    collections.namedtuple(
        'PubSubCallbackNamedTuple',
        (
            'topic',  # String. The pubsub topic to receive build status change.
            'auth_token',  # String. Authentication token to get pushed back.
            'user_data',  # jsonish dict. Any data to get pushed back.
        ))):
  """Represents the info for the PubSub callback."""

  def ToRequestParameter(self):
    return {
        'topic': self.topic,
        'auth_token': self.auth_token,
        'user_data': json.dumps(self.user_data, sort_keys=True),
    }


class TryJob(
    collections.namedtuple(
        'TryJobNamedTuple',
        (
            'master_name',  # Tryserver master name as the build bucket name.
            'builder_name',  # Tryserver builder name of the try-job.
            'properties',  # Build properties for the try-job.
            'tags',  # Tags to flag the try-job for searching or monitoring.
            'cache_name',  # Optional. Nme of the cache in the Swarmingbot.
            'dimensions',  # Optional. Dimensions used to match a Swarmingbot.
            'pubsub_callback',  # Optional. PubSub callback info.
            'priority',  # Optional swarming priority 20 (high) to 255 (low).
            'expiration_secs',  # Optional seconds to expire the try job. i.e.
            # give up if no bot becomes available when the
            # task has been pending this long.
        ))):
  """Represents a try-job to be triggered through Buildbucket.

  Tag for "user_agent" should not be set, as it will be added automatically.
  """

  def __new__(
      cls,  # This is to make the last 3 tuple members optional.
      master_name,
      builder_name,
      properties,
      tags,
      cache_name=None,
      dimensions=None,
      pubsub_callback=None,
      priority=None,
      expiration_secs=None):
    return super(cls, TryJob).__new__(
        cls, master_name, builder_name, properties, tags, cache_name,
        dimensions, pubsub_callback, priority, expiration_secs)

  def _AddSwarmbucketOverrides(self, parameters):
    assert self.cache_name
    parameters['swarming'] = {
        'override_builder_cfg': {
            'caches': [{
                'name': self.cache_name,
                'path': 'builder'
            }],
        }
    }
    if 'recipe' in self.properties:
      parameters['swarming']['override_builder_cfg']['recipe'] = {
          'name': self.properties['recipe']
      }

    if self.priority is not None:
      priority, constrained = constrain(self.priority, 1, 255)
      if constrained:
        logging.warning(
            'Priority in swarming is limited to values between 1 and 255, '
            'constraining %d to %d' % (self.priority, priority))
      parameters['swarming']['override_builder_cfg']['priority'] = priority

    if self.expiration_secs is not None:
      parameters['swarming']['override_builder_cfg']['expiration_secs'] = int(
          self.expiration_secs)

    if self.dimensions:
      parameters['swarming']['override_builder_cfg']['dimensions'] = (
          self.dimensions)

  def ToBuildbucketRequest(self):
    parameters_json = {
        'builder_name': self.builder_name,
        'properties': self.properties,
    }

    tags = self.tags[:]
    tags.append('user_agent:findit')

    if self.is_swarmbucket_build:
      self._AddSwarmbucketOverrides(parameters_json)

    request = {
        'bucket': _GetBucketName(self.master_name),
        'parameters_json': json.dumps(parameters_json),
        'tags': tags,
    }
    if self.pubsub_callback:
      request['pubsub_callback'] = self.pubsub_callback.ToRequestParameter()
    return request

  @property
  def is_swarmbucket_build(self):
    bucket = _GetBucketName(self.master_name)
    return bucket.startswith(_LUCI_PREFIX)


class BuildbucketBuild(object):
  """Represents a build triggered through Buildbucket.

  This corresponds to the Build in Buildbucket.
  """

  # Build statuses.
  SCHEDULED = 'SCHEDULED'
  STARTED = 'STARTED'
  COMPLETED = 'COMPLETED'

  def __init__(self, raw_json_data):
    self.response = raw_json_data
    self.id = raw_json_data.get('id')
    self.url = raw_json_data.get('url')
    self.status = raw_json_data.get('status')
    self.request_time = raw_json_data.get('created_ts')
    self.start_time = raw_json_data.get('started_ts')
    self.end_time = raw_json_data.get('completed_ts')


class BuildbucketError(object):
  """Represents an error returned by Buildbucket."""

  # Error reasons.
  BUILD_NOT_FOUND = 'BUILD_NOT_FOUND'
  INVALID_INPUT = 'INVALID_INPUT'

  def __init__(self, raw_json_data):
    self.response = raw_json_data
    self.reason = raw_json_data.get('reason')
    self.message = raw_json_data.get('message')


def _ConvertFuturesToResults(json_results):
  """Converts the given futures to results.

  Args:
    json_results (list): a list of dict each representing a Buildbucket Build.

  Returns:
    A list of tuple (error, build) in the same order as the given results.
      error: an instance of BuildbucketError. None if no error occurred.
      build: an instance of BuildbucketBuild. None if error occurred.
  """
  results = []
  for json_result in json_results:
    logging.info('Try-job result:\n%s', json.dumps(json_result, indent=2))
    error = json_result.get('error')
    if error:
      results.append((BuildbucketError(error), None))
    else:
      results.append((None, BuildbucketBuild(json_result.get('build'))))
  return results


def _GetHeaders():
  return {
      'Content-Type': 'application/json; charset=UTF-8',
  }


def TriggerTryJobs(try_jobs):
  """Triggers try-job in a batch.

  Args:
    try_jobs (list): a list of TryJob instances.

  Returns:
    A list of tuple (error, build) in the same order as the given try-jobs.
      error: an instance of BuildbucketError. None if no error occurred.
      build: an instance of BuildbucketBuild. None if error occurred.
  """
  json_results = []

  for try_job in try_jobs:
    status_code, content, _response_headers = FinditHttpClient().Put(
        _BUILDBUCKET_PUT_GET_ENDPOINT,
        json.dumps(try_job.ToBuildbucketRequest()),
        headers=_GetHeaders())
    if status_code == 200:  # pragma: no cover
      json_results.append(json.loads(content))
    else:
      error_content = {'error': {'reason': status_code, 'message': content}}
      json_results.append(error_content)

  return _ConvertFuturesToResults(json_results)


def GetTryJobs(build_ids):
  """Returns the try-job builds for the given build ids.

  Args:
    build_ids (list): a list of build ids returned by Buildbucket.

  Returns:
    A list of tuple (error, build) in the same order as given build ids.
      error: an instance of BuildbucketError. None if no error occurred.
      build: an instance of BuildbucketBuild. None if error occurred.
  """
  json_results = []

  for build_id in build_ids:
    status_code, content, _response_headers = FinditHttpClient().Get(
        _BUILDBUCKET_PUT_GET_ENDPOINT + '/' + build_id, headers=_GetHeaders())
    if status_code == 200:  # pragma: no cover
      json_results.append(json.loads(content))
    else:
      error_content = {'error': {'reason': status_code, 'message': content}}
      json_results.append(error_content)

  return _ConvertFuturesToResults(json_results)


def GetV2Build(build_id, fields=None):
  """Get a buildbucket build from the v2 API.

  Args:
    build_id (str): Buildbucket id of the build to get.
    fields (google.protobuf.FieldMask): Mask for the paths to get, as not all
        fields are populated by default (such as steps).

  Returns:
    A buildbucket_proto.build_pb2.Build proto.
  """
  request = GetBuildRequest(id=int(build_id), fields=fields)
  status_code, content, response_headers = FinditHttpClient().Post(
      _BUILDBUCKET_V2_GET_BUILD_ENDPOINT,
      request.SerializeToString(),
      headers={'Content-Type': 'application/prpc; encoding=binary'})
  if status_code == 200 and response_headers.get('X-Prpc-Grpc-Code') == GRPC_OK:
    result = Build()
    result.ParseFromString(content)
    return result
  logging.warning('Unexpected prpc code: %s',
                  response_headers.get('X-Prpc-Grpc-Code'))
  return None


def GetBuildNumberFromBuildId(build_id):
  """Extracts the build number given a build id."""
  try:
    build_proto = GetV2Build(build_id)
    build_properties = dict(build_proto.output.properties.items())
    return int(build_properties['buildnumber'])
  except Exception as e:
    logging.error('Unable to get build number from build id %s' % build_id)
    logging.error(e.message)
    return None


def GetV2BuildByBuilderAndBuildNumber(project,
                                      bucket,
                                      builder_name,
                                      build_number,
                                      fields=None):
  """Get a buildbucket build from the v2 API by build info."""
  builder = BuilderID(project=project, bucket=bucket, builder=builder_name)
  request = GetBuildRequest(
      builder=builder, build_number=build_number, fields=fields)
  status_code, content, response_headers = FinditHttpClient().Post(
      _BUILDBUCKET_V2_GET_BUILD_ENDPOINT,
      request.SerializeToString(),
      headers={'Content-Type': 'application/prpc; encoding=binary'})
  if status_code == 200 and response_headers.get('X-Prpc-Grpc-Code') == GRPC_OK:
    result = Build()
    result.ParseFromString(content)
    return result
  logging.warning('Unexpected prpc code: %s',
                  response_headers.get('X-Prpc-Grpc-Code'))
  return None


def SearchV2BuildsOnBuilder(builder,
                            status=None,
                            build_range=None,
                            create_time_range=None,
                            page_size=None,
                            fields=None):
  """Searches builds on a builder.

  Args:
    builder (build_pb2.BuilderID): Id of the builder, with project, bucket and
      builder_name.
    status (common_pb2.Status): Status of searched builds, like
      common_pb2.FAILURE. common_pb2.ENDED_MASK can be used when search for all
      completed builds regardless of status.
    build_range (tuple): A pair of build_ids for the range of the build.
    create_time_range (tuple): A pair of datetimes for the range of the build
      create_time. Both ends are optional. The format is like:
      (
         # Left bound of the range, inclusive.
         datetime(2019, 4, 8),
         # Right bound of the range, exclusive.
        datetime(2019, 4, 9)
      )
    page_size (int): Number of builds returned in one request.
    fields (google.protobuf.FieldMask): Mask for the paths to get, as not all
        fields are populated by default.
  """
  predicate = BuildPredicate(builder=builder, status=status)

  if build_range:
    if build_range[0]:  # pragma: no cover.
      # Left bound specified.
      predicate.build.start_build_id = int(build_range[0])
    if build_range[1]:
      # Right bound specified.
      predicate.build.end_build_id = int(build_range[1])

  if create_time_range:
    if create_time_range[0]:  # pragma: no cover.
      # Left bound specified.
      predicate.create_time.start_time.FromDatetime(create_time_range[0])
    if create_time_range[1]:
      # Right bound specified.
      predicate.create_time.end_time.FromDatetime(create_time_range[1])
  request = SearchBuildsRequest(
      predicate=predicate, page_size=page_size, fields=fields)

  status_code, content, response_headers = FinditHttpClient().Post(
      _BUILDBUCKET_V2_SEARCH_BUILDS_ENDPOINT,
      request.SerializeToString(),
      headers={'Content-Type': 'application/prpc; encoding=binary'})
  if status_code == 200 and response_headers.get('X-Prpc-Grpc-Code') == GRPC_OK:
    result = SearchBuildsResponse()
    result.ParseFromString(content)
    return result
  logging.warning('Unexpected status_code: %d and prpc code: %s', status_code,
                  response_headers.get('X-Prpc-Grpc-Code'))
  return None


def TriggerV2Build(builder,
                   gitiles_commit,
                   properties,
                   tags=None,
                   dimensions=None):
  """Triggers a build using buildbucket v2 API.

  Args:
    builder (build_pb2.BuilderID): Information about the builder the
      build runs on.
    gitiles_commit (common_pb2.GitilesCommit): Input commit the build runs.
    properties (dict): Input properties of the build.
    tags (list of dict): Tags for the build. In the format:
      [
        {
          'key': 'tag-key',
          'value': 'tag-value'
        },
        ...
      ]
    dimensions (list of dict): configured dimensions of the build. Format:
      [
        {
          'key': 'dimension-key',
          'value': 'dimension-value'
        },
        ...
      ]
  """
  request = ScheduleBuildRequest(
      builder=builder,
      gitiles_commit=gitiles_commit,
      tags=tags or [],
      dimensions=dimensions or [])
  request.properties.update(properties)

  status_code, content, response_headers = FinditHttpClient().Post(
      _BUILDBUCKET_V2_SCHEDULE_BUILD_ENDPOINT,
      request.SerializeToString(),
      headers={'Content-Type': 'application/prpc; encoding=binary'})

  if status_code == 200 and response_headers.get('X-Prpc-Grpc-Code') == GRPC_OK:
    result = Build()
    result.ParseFromString(content)
    return result

  logging.warning('Unexpected status_code: %d and prpc code: %s', status_code,
                  response_headers.get('X-Prpc-Grpc-Code'))
  return None
