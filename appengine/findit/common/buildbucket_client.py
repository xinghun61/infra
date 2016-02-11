# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""""Serves as a client for selected APIs in Buildbucket."""

import collections
import json
import logging

from common.http_client_appengine import HttpClientAppengine as HttpClient
from waterfall import auth_util


# TODO: save these settings in datastore and create a role account.
_ROLE_EMAIL = 'IF_BREAK_CONTACT_stgao@chromium.org'
_BUILDBUCKET_HOST = 'cr-buildbucket.appspot.com'
_BUILDBUCKET_PUT_GET_ENDPOINT = (
    'https://{hostname}/_ah/api/buildbucket/v1/builds'.format(
        hostname=_BUILDBUCKET_HOST))


def _GetBucketName(master_name):
  """Converts shortened master name to full master name.

  Buildbucket uses full master name (master.tryserver.chromium.linux) as bucket
  name, while Findit uses shortened master name (tryserver.chromium.linux).
  """
  prefix = 'master.'
  if master_name.startswith(prefix):
    return master_name
  return '%s%s' % (prefix, master_name)


class TryJob(collections.namedtuple(
    'TryJobNamedTuple',
    ('master_name', 'builder_name', 'revision', 'properties', 'tags'))):
  """Represents a try-job to be triggered through Buildbucket.

  Tag for "user_agent" should not be set, as it will be added automatically.
  """

  def ToBuildbucketRequest(self):
    parameters_json = {
        'builder_name': self.builder_name,
        'properties': self.properties,
    }
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

    return {
        'bucket': _GetBucketName(self.master_name),
        'parameters_json': json.dumps(parameters_json),
        'tags': tags,
    }


class BuildbucketBuild(object):
  """Represents a build triggered through Buildbucket.

  This corresponds to the Build in Buildbucket.
  """

  # Build statuses.
  SCHEDULED = 'SCHEDULED'
  STARTED = 'STARTED'
  COMPLETED = 'COMPLETED'

  def __init__(self, raw_json_data):
    self.id = raw_json_data.get('id')
    self.url = raw_json_data.get('url')
    self.status = raw_json_data.get('status')
    self.request_time = raw_json_data.get('created_ts')
    self.updated_time = raw_json_data.get('updated_ts')
    self.end_time = raw_json_data.get('completed_ts')
    result_details_json = json.loads(
        raw_json_data.get('result_details_json', '{}')) or {}
    self.report = result_details_json.get('properties', {}).get('report', {})


class BuildbucketError(object):
  """Represents an error returned by Buildbucket."""

  # Error reasons.
  BUILD_NOT_FOUND = 'BUILD_NOT_FOUND'
  INVALID_INPUT = 'INVALID_INPUT'

  def __init__(self, raw_json_data):
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
  headers = {
      'Authorization': 'Bearer ' + auth_util.GetAuthToken(),
      'Content-Type': 'application/json; charset=UTF-8'
  }

  for try_job in try_jobs:
    status_code, content = HttpClient().Put(
        _BUILDBUCKET_PUT_GET_ENDPOINT,
        json.dumps(try_job.ToBuildbucketRequest()), headers=headers)
    if status_code == 200:  # pragma: no cover
      json_results.append(json.loads(content))
    else:
      error_content = {
          'error': {
              'reason': status_code,
              'message': content
          }
      }
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
    status_code, content = HttpClient().Get(
        _BUILDBUCKET_PUT_GET_ENDPOINT + '/' + build_id, headers=headers)
    if status_code == 200:  # pragma: no cover
      json_results.append(json.loads(content))
    else:
      error_content = {
          'error': {
              'reason': status_code,
              'message': content
          }
      }
      json_results.append(error_content)

  return _ConvertFuturesToResults(json_results)
