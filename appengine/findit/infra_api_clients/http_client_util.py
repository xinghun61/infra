# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Sharable functions for sending requests using http client."""

import json


def SendRequestToServer(url, http_client, post_data=None):
  """Sends GET/POST request to arbitrary url and returns response content.

  Args:
    url (str): The url to send the request to.
    http_client (HttpClient): The httpclient object with which to make the
      server calls.
    post_data (dict): Data/params to send with the request, if any.
  Returns:
    content (dict), error (dict): the content from
      the server and the last error encountered trying to retrieve it.
  """
  error = None

  headers = {}
  if post_data:
    post_data = json.dumps(post_data, sort_keys=True, separators=(',', ':'))
    headers['Content-Type'] = 'application/json; charset=UTF-8'
    headers['Content-Length'] = len(post_data)

  if post_data:
    status_code, content, _response_headers = http_client.Post(
        url, post_data, headers=headers)
  else:
    status_code, content, _response_headers = http_client.Get(
        url, headers=headers)
  if status_code == 200:
    # Also return the last error encountered to be handled in the calling
    # code.
    return content, error
  else:
    # The retry upon 50x (501 excluded) is automatically handled in the
    # underlying http_client, which by default retries 5 times with
    # exponential backoff.
    return None, {
        'code': status_code,
        'message': 'Unexpected status code from http request'
    }
