# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Client library to interact with isolate API."""

import base64
import json
import zlib

from infra_api_clients import http_client_util


def FetchFileFromIsolatedServer(digest, name_space, isolated_server,
                                http_client):
  """Sends retrieve request to isolated server and returns response content.
  Args:
    digest(str): Hash to file for retrieve request.
    name_space(str): Name space info for retrieve request.
    isolated_server(str): Host to isolate server.
    http_client(RetryHttpClient): http client to send the request.
  """
  post_data = {'digest': digest, 'namespace': {'namespace': name_space}}
  url = '%s/_ah/api/isolateservice/v1/retrieve' % isolated_server

  content, error = http_client_util.SendRequestToServer(
      url, http_client, post_data=post_data)

  if error:
    return None, error

  json_content = json.loads(content)
  file_url = json_content.get('url')
  error = None
  assert file_url or json_content.get(
      'content'), 'Response from isolate is missing both url and content.'

  if file_url:
    compressed_content, error = http_client_util.SendRequestToServer(
        file_url, http_client)
  else:
    compressed_content = base64.b64decode(json_content['content'])
  return zlib.decompress(
      compressed_content) if compressed_content else None, error
