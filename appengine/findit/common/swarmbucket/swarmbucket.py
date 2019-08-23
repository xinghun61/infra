# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Wrap swarmbucket-specific APIs for Findit's use."""

import json

from common.findit_http_client import FinditHttpClient
from gae_libs.caches import CompressedMemCache
from libs.cache_decorator import Cached

_DEFAULT_SWARMBUCKET_SERVICE_URL = ('https://cr-buildbucket.appspot.com'
                                    '/_ah/api/swarmbucket/v1')
# Note that current trybots only need to match dimensions to build the targets,
# as the tests themselves happen on regular swarming bots.
_DIMENSIONS_TO_MATCH_FOR_TRYBOT = frozenset(['os', 'cpu'])


def _CallSwarmbucketAPI(base_url, api_name, request_data, method='POST'):
  assert method in ['POST', 'GET'], 'Only POST and GET requests are supported'
  endpoint = '%s/%s' % (base_url, api_name)
  headers = {'Content-Type': 'application/json; charset=UTF-8'}
  if method == 'POST':
    data = json.dumps(request_data)
    status_code, content, _response_headers = FinditHttpClient().Post(
        endpoint, data, headers=headers)
  elif method == 'GET':
    status_code, content, _response_headers = FinditHttpClient().Get(
        endpoint, request_data, headers=headers)
  if status_code == 200:
    return json.loads(content)
  return {}


def GetDimensionsForBuilder(
    bucket,
    builder,
    service_url=_DEFAULT_SWARMBUCKET_SERVICE_URL,
    dimensions_whitelist=_DIMENSIONS_TO_MATCH_FOR_TRYBOT):
  """Gets the dimensions for replicating builder's configuration.

  Args:
    bucket(str): The name of the bucket where the builder is configured.
    builder(str): The name of the builder whose dimensions we're after.
    service_url(str): The url for the swarmbucket service, defaults to the
        production service url.
    dimensions_whitelist(iterable of str): Which dimensions to return, set None
       to return all.

  Returns:
    A list of colon separated strings of the form "key:value".
  """
  request = {
      'build_request': {
          'bucket': bucket,
          'parameters_json': json.dumps({
              'builder_name': builder
          })
      }
  }

  response = _CallSwarmbucketAPI(service_url, 'get_task_def', request)
  # The response to get task definition contains a single key('task_definition')
  # and its value is a serialized dict that contains, among other things, a
  # 'properties' key wich in turn contains a 'dimensions' key.
  #
  # For more information, refer to buildbucket's code for this in:
  # https://cs.chromium.org/search/?q=%22def+_create_task_def_async%22&ssfr=1&sq=package:chromium&type=cs
  task_def = json.loads(response.get('task_definition', '{}'))
  if not task_def:
    return []
  dimensions = task_def['task_slices'][0].get('properties', {}).get(
      'dimensions', [])
  if dimensions_whitelist is None:
    return [
        '%s:%s' % (d.get('key', ''), d.get('value', '')) for d in dimensions
    ]
  else:
    return [
        '%s:%s' % (d.get('key', ''), d.get('value', ''))
        for d in dimensions
        if d.get('key') in dimensions_whitelist
    ]


# Cache responses for 10 minutes.
@Cached(
    CompressedMemCache(), namespace='swarmbucket-get-builders', expire_time=600)
def GetBuilders(bucket, service_url=_DEFAULT_SWARMBUCKET_SERVICE_URL):
  """Get the list of builder names for a given bucket.

  Args:
    bucket(str): The name of the bucket where the builders are configured.
    service_url(str): The url for the swarmbucket service, defaults to the
        production service url.

  Returns:
    A list of str where each value is the name of a builder in the given bucket.
  """
  request = {'bucket': bucket}
  response = _CallSwarmbucketAPI(service_url, 'builders', request, method='GET')
  assert response, 'Could not retrieve builders for %s via swarmbucket' % bucket
  return {b.get('name'): b for b in response['buckets'][0]['builders']}


# Cache responses for 1 hour.
@Cached(
    CompressedMemCache(), namespace='swarmbucket-get-masters', expire_time=3600)
def GetMasters(bucket, service_url=_DEFAULT_SWARMBUCKET_SERVICE_URL):
  """Get the list of master names for a given bucket.

  Args:
    bucket(str): The name of the bucket where the builders are configured.
    service_url(str): The url for the swarmbucket service, defaults to the
        production service url.

  Returns:
    A list of str where each value is the name of a builder in the given bucket.
  """
  request = {'bucket': bucket}
  response = _CallSwarmbucketAPI(service_url, 'builders', request, method='GET')
  assert response, 'Could not retrieve builders for %s via swarmbucket' % bucket
  masters = set()
  for b in response['buckets'][0]['builders']:
    properties = json.loads(b.get('properties_json') or '{}')
    if properties.get('mastername'):
      masters.add(properties['mastername'])
  return list(masters)
