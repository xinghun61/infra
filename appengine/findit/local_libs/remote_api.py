# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is used to set up Remote API to use services on App Engine.

After setup, available services include datastore, task queue, etc.
You may be prompted for credentials during the remote query or the like.
And you could use Remote API only when you are one of the project members.

For detail on usage of Remote API, please refer to:
  https://cloud.google.com/appengine/docs/python/tools/remoteapi
"""
import os
import socket
import sys

# This relative import is because We don't want ``remote_api`` to insert any
# root directory paths in sys paths, so that it can mess up other project who
# using this ``remote_api``, for example, Predator.
import script_util  # pylint: disable=W0403
script_util.SetAppEnginePaths()

from google.appengine.api import urlfetch
from google.appengine.ext.remote_api import remote_api_stub


# TODO(crbug.com/662540): Add unittests.
def SetTimeoutForUrlOperations(
    url_blocking_operations_timeout=600):  # pragma: no cover
  """Set timeout for url operations (socket, appengine db)."""
  socket.setdefaulttimeout(url_blocking_operations_timeout)
  urlfetch.set_default_fetch_deadline(url_blocking_operations_timeout)


# TODO(crbug.com/662540): Add unittests.
def EnableRemoteApi(app_id='findit-for-me'):  # pragma: no cover
  """Enable appengine services through remote API.

  Args:
    app_id (str): The appengine ID without '.appspot.com', eg. findit-for-me.
  """
  if hasattr(EnableRemoteApi, app_id):
    return

  SetTimeoutForUrlOperations()

  remote_api_stub.ConfigureRemoteApiForOAuth(
      '%s.appspot.com' % app_id,
      '/_ah/remote_api',
      secure=True,
      save_cookies=True)
  setattr(EnableRemoteApi, app_id, True)

def EnableFinditRemoteApi():  # pragma: no cover
  script_util.SetUpSystemPaths()
  EnableRemoteApi(app_id='findit-for-me')