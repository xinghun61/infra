#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import code
import getpass
import logging
import os
import sys

ROOT = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
LIB = os.path.join(ROOT, '..', 'google_appengine', 'lib')
sys.path.append(os.path.join(ROOT, '..', 'google_appengine'))
sys.path.append(os.path.join(LIB, 'yaml', 'lib'))
sys.path.append(os.path.join(LIB, 'fancy_urllib'))
sys.path.append(os.path.join(LIB, 'simplejson'))
sys.path.append(os.path.join(LIB, 'webob'))
sys.path.append(ROOT)


def auth_func():
  user = os.environ.get('EMAIL_ADDRESS')
  if user:
    print('User: %s' % user)
  else:
    user = raw_input('Username:')
  return user, getpass.getpass('Password:')


def main():
  if len(sys.argv) < 2:
    app_id = 'chromium-status'
  else:
    app_id = sys.argv[1]
  if len(sys.argv) > 2:
    host = sys.argv[2]
  else:
    host = '%s.appspot.com' % app_id
  logging.basicConfig(level=logging.ERROR)

  # pylint: disable=W0612
  from google.appengine.ext.remote_api import remote_api_stub
  from google.appengine.api import memcache
  from google.appengine.ext import db
  remote_api_stub.ConfigureRemoteDatastore(
      app_id, '/_ah/remote_api', auth_func, host)

  import base_page
  import breakpad
  import status
  code.interact(
      'App Engine interactive console for %s' % (app_id,), None, locals())


if __name__ == '__main__':
  sys.exit(main())
