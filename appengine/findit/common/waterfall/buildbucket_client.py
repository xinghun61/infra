# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""""Serves as a client for selected APIs in Buildbucket."""

import collections
import json
import logging
import urllib

from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.rpc_pb2 import GetBuildRequest
from common.findit_http_client import FinditHttpClient
from gae_libs.http import auth_util
from libs.math.integers import constrain

# https://github.com/grpc/grpc-go/blob/master/codes/codes.go
GRPC_OK = '0'

# TODO: save these settings in datastore and create a role account.
_BUILDBUCKET_HOST = 'cr-buildbucket.appspot.com'
_BUILDBUCKET_PUT_GET_ENDPOINT = (
    'https://{hostname}/_ah/api/buildbucket/v1/builds'.format(
        hostname=_BUILDBUCKET_HOST))
_LUCI_PREFIX = 'luci.'
_BUILDBUCKET_SEARCH_ENDPOINT = (
    'https://{hostname}/_ah/api/buildbucket/v1/search'.format(
        hostname=_BUILDBUCKET_HOST))
_BUILDBUCKET_V2_GET_BUILD_ENDPOINT = (
    'https://{hostname}/prpc/buildbucket.v2.Builds/GetBuild'.format(
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
            # Additional build parameters that do not fit into build properties,
            # e.g. it is more than 1024 chars for a buildbot build property.
            'additional_build_parameters',
            'cache_name',  # Optional. Nme of the cache in the Swarmingbot.
            'dimensions',  # Optional. Dimensions used to match a Swarmingbot.
            'pubsub_callback',  # Optional. PubSub callback info.
            'priority',  # Optional swarming priority 1 (high) thru 200 (low).
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
      additional_build_parameters,
      cache_name=None,
      dimensions=None,
      pubsub_callback=None,
      priority=None):
    return super(cls,
                 TryJob).__new__(cls, master_name, builder_name, properties,
                                 tags, additional_build_parameters, cache_name,
                                 dimensions, pubsub_callback, priority)

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

    if self.dimensions:
      parameters['swarming']['override_builder_cfg']['dimensions'] = (
          self.dimensions)

  def ToBuildbucketRequest(self):
    parameters_json = {
        'builder_name': self.builder_name,
        'properties': self.properties,
    }
    if self.additional_build_parameters:
      parameters_json['additional_build_parameters'] = (
          self.additional_build_parameters)

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


def SearchBuilds(tags):
  """Returns data for builds that are searched by tags.

  Args:
    tags (list): A list of tags and their values in the format as
      [('tag', 'buildername:Linux Tests'].

  Returns:
    data (dict): A dict of builds' info.
  """
  tag_str = urllib.urlencode(tags)
  status_code, content, _response_headers = FinditHttpClient().Get(
      _BUILDBUCKET_SEARCH_ENDPOINT + '?' + tag_str, headers=_GetHeaders())
  if status_code == 200:
    try:
      return json.loads(content or '{}')
    except (ValueError, TypeError):
      logging.exception('Failed to search for builds using tags %s', tag_str)
  else:
    logging.error(
        'Failed to search for builds using tags %s with status_code %d.',
        tag_str, status_code)
  return None


def GetV2Build(build_id, fields=None):
  """Get a buildbucket build from the v2 API.

  Args:
    build_id (int64): Buildbucket id of the build to get.
    fields (google.protobuf.FieldMask): Mask for the paths to get, as not all
        fields are populated by default (such as steps).

  Returns:
    A buildbucket_proto.build_pb2.Build proto.
  """
  request = GetBuildRequest(id=build_id, fields=fields)
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
