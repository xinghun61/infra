# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

_RESPONSE_PREFIX = ')]}\'\n'


def DownloadData(url, data, http_client, **kwargs):
  """Downloads data from rpc endpoints like Logdog or Milo."""

  headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

  status_code, response = http_client.Post(
      url, json.dumps(data), headers=headers, **kwargs)
  if status_code != 200 or not response:
    logging.error('Post request to %s failed' % url)
    return None

  return response


def _GetResultJson(response):
  """Converts response from rpc endpoints to json format."""

  if response.startswith(_RESPONSE_PREFIX):
    # Removes extra _RESPONSE_PREFIX so we can get json data.
    return response[len(_RESPONSE_PREFIX):]
  return response


def DownloadJsonData(url, data, http_client, **kwargs):
  """Downloads data from rpc endpoints and converts response in json format.

  Args:
    url(str): The url to request.
    data(dict): Json-serializable data to pass to the rpc endpoint via post.
    http_client(libs.http.retry_http_client): Http client instance.
    kwargs: Piped to the .Post call done to the http client.

  Returns:
    The response deserialized from json into a python object (likely a dict).
  """
  response = DownloadData(url, data, http_client, **kwargs)
  return _GetResultJson(response) if response else None
