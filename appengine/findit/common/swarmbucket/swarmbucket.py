# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Wrap swarmbucket-specific APIs for Findit's use."""

import json

from common.findit_http_client import FinditHttpClient

_DEFAULT_SWARMBUCKET_SERVICE_URL = ('https://cr-buildbucket.appspot.com'
                                    '/_ah/api/swarmbucket/v1')
_DEFAULT_WATERFALL_BUCKET = 'luci.chromium.ci'


def _CallSwarmbucketAPI(base_url, api_name, request_data):
  endpoint = '%s/%s' % (base_url, api_name)
  data = json.dumps(request_data)
  headers = {'Content-Type': 'application/json; charset=UTF-8'}
  status_code, body = FinditHttpClient().Post(endpoint, data, headers=headers)
  if status_code == 200:
    return json.loads(body)
  return {}


def GetDimensionsForBuilder(builder,
                            bucket=_DEFAULT_WATERFALL_BUCKET,
                            service_url=_DEFAULT_SWARMBUCKET_SERVICE_URL):
  """Gets the dimensions for replicating builder's configuration.

  Args:
    builder(str): The name of the builder whose dimensions we're after.
    bucket(str): The name of the bucket where the builder is configured,
        defaults to luci.chromium.ci.
    service_url(str): The url for the swarmbucket service, defaults to the
        production service url.
  Returns: A list of colon separated strings of the form "key:value".
  """
  request = {
      'bucket': bucket,
      'parameters_json': json.dumps({
          'builder_name': builder
      })
  }

  response = _CallSwarmbucketAPI(service_url, 'get_task_def', request)
  # The response to get task definition contains a single key('task_definition')
  # and its value is a serialized dict that contains, among other things, a
  # 'properties' key wich in turn contains a 'dimensions' key.
  #
  # For more information, refer to buildbucket's code for this in:
  # https://cs.chromium.org/search/?q=%22def+_create_task_def_async%22&ssfr=1&sq=package:chromium&type=cs
  task_def = json.loads(response.get('task_definition', '{}'))
  dimensions = task_def.get('properties', {}).get('dimensions', [])
  return ['%s:%s' % (d.get('key', ''), d.get('value', '')) for d in dimensions]
