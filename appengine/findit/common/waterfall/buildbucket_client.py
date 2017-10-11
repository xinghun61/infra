# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""""Serves as a client for selected APIs in Buildbucket."""

import collections
import json
import logging

from gae_libs.http import auth_util

from common.findit_http_client import FinditHttpClient
from common.waterfall.pubsub_callback import MakeTryJobPubsubCallback

# TODO: save these settings in datastore and create a role account.
_ROLE_EMAIL = 'IF_BREAK_CONTACT_stgao@chromium.org'
_BUILDBUCKET_HOST = 'cr-buildbucket.appspot.com'
_BUILDBUCKET_PUT_GET_ENDPOINT = (
    'https://{hostname}/api/buildbucket/v1/builds'.format(
        hostname=_BUILDBUCKET_HOST))
_LUCI_PREFIX = 'luci.'


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


class TryJob(
    collections.namedtuple('TryJobNamedTuple',
                           ('master_name', 'builder_name', 'revision',
                            'properties', 'tags', 'additional_build_parameters',
                            'cache_name', 'dimensions'))):
  """Represents a try-job to be triggered through Buildbucket.

  Tag for "user_agent" should not be set, as it will be added automatically.
  """

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
    if self.dimensions:
      parameters['swarming']['override_builder_cfg']['dimensions'] = (
          self.dimensions)

  def ToBuildbucketRequest(self, notification_id=''):
    parameters_json = {
        'builder_name': self.builder_name,
        'properties': self.properties,
    }
    if self.additional_build_parameters:
      parameters_json['additional_build_parameters'] = (
          self.additional_build_parameters)
    if self.revision:
      parameters_json['changes'] = [
          {
              'author': {
                  'email': _ROLE_EMAIL,
              },
              'revision': self.revision,
          },
      ]

    tags = self.tags[:]
    tags.append('user_agent:findit')

    if self.is_swarmbucket_build:
      self._AddSwarmbucketOverrides(parameters_json)

    return {
        'bucket': _GetBucketName(self.master_name),
        'parameters_json': json.dumps(parameters_json),
        'tags': tags,
        'pubsub_callback': MakeTryJobPubsubCallback(notification_id),
    }

  @property
  def is_swarmbucket_build(self):
    bucket = _GetBucketName(self.master_name)
    return bucket.startswith(_LUCI_PREFIX)


# Make the last two members optional.
TryJob.__new__.__defaults__ = (None, None)


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
    self.updated_time = raw_json_data.get('updated_ts')
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
    json_results (dict): a map from a key (either build id or revision) to a
    response for the put or get request to Buildbucket.

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


def TriggerTryJobs(try_jobs, notification_id=''):
  """Triggers try-job in a batch.

  Args:
    try_jobs (list): a list of TryJob instances.
    notification_id (str): id of the pipeline that trigger the try job.
      It could be empty if the try job is triggered by periodic_bot_update.

  Returns:
    A list of tuple (error, build) in the same order as the given try-jobs.
      error: an instance of BuildbucketError. None if no error occurred.
      build: an instance of BuildbucketBuild. None if error occurred.
  """
  json_results = []
  headers = {
      'Authorization': 'Bearer ' + auth_util.GetAuthToken(),
      'Content-Type': 'application/json; charset=UTF-8'
  }

  for try_job in try_jobs:
    status_code, content = FinditHttpClient().Put(
        _BUILDBUCKET_PUT_GET_ENDPOINT,
        json.dumps(try_job.ToBuildbucketRequest(notification_id)),
        headers=headers)
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
  headers = {
      'Authorization': 'Bearer ' + auth_util.GetAuthToken(),
      'Content-Type': 'application/json; charset=UTF-8'
  }

  for build_id in build_ids:
    status_code, content = FinditHttpClient().Get(
        _BUILDBUCKET_PUT_GET_ENDPOINT + '/' + build_id, headers=headers)
    if status_code == 200:  # pragma: no cover
      json_results.append(json.loads(content))
    else:
      error_content = {'error': {'reason': status_code, 'message': content}}
      json_results.append(error_content)

  return _ConvertFuturesToResults(json_results)
