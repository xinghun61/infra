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


_FINDIT_ROOT_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
_APPNGINE_SDK_DIR = os.path.join(_FINDIT_ROOT_DIR, os.path.pardir,
                                 os.path.pardir, os.path.pardir,
                                 'google_appengine')


# Add App Engine SDK dir to sys.path.
sys.path.insert(1, _APPNGINE_SDK_DIR)
import dev_appserver
dev_appserver.fix_sys_path()


# Add Findit root dir to sys.path so that modules in Findit would be available.
sys.path.insert(1, _FINDIT_ROOT_DIR)


from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext.remote_api import remote_api_stub


def SetTimeoutForUrlOperations(url_blocking_operations_timeout=600):
  """Set timeout for url operations (socket, appengine db)."""
  socket.setdefaulttimeout(url_blocking_operations_timeout)
  urlfetch.set_default_fetch_deadline(url_blocking_operations_timeout)


def EnableRemoteApi(app_id='findit-for-me'):
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
