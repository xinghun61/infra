# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This is a client to talk to the APIs in crrev.com"""

import json

_CRREV_HOST = 'https://cr-rev.appspot.com'
_REDIRECT_API = '%s/_ah/api/crrev/v1/redirect' % _CRREV_HOST


def RedirectByCommitPosition(http_client, commit_position):
  """Returns the info for a Chromium commit position.

  Args:
    http_client (libs.http.RetryHttpClient): the http client to send request.
    commit_position (int): the Chromium commit position of a git commit.

  Returns:
    A dict containing the following info, or None if there is error.
      {
        "git_sha": "the sha of the git commit",
        "repo_url": "https://chromium.googlesource.com/chromium/src/"
      }
  """
  url = _REDIRECT_API + '/' + str(commit_position)
  status_code, content, _response_headers = http_client.Get(url)
  if status_code != 200:
    return None
  data = json.loads(content)
  return {
      'git_sha': data['git_sha'],
      'repo_url': data['repo_url'],
  }
