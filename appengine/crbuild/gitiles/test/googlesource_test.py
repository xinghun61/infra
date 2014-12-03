# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import json

from gitiles.googlesource import (GoogleSourceServiceClient,
                                  AuthenticationError, Error)
from test import CrBuildTestCase


HOSTNAME = 'chromium.googlesource.com'
PATH = 'resource'
URL = 'https://%s/a/%s' % (HOSTNAME, PATH)


class GoogleSourceClientTestCase(CrBuildTestCase):
  def test_fetch(self):
    req_body = {'b': 2}
    self.urlfetch_fetch.return_value.content = ')]}\'{"a":1}'
    self.urlfetch_fetch.return_value.status_code = httplib.OK
    client = GoogleSourceServiceClient(HOSTNAME)
    actual = client._fetch(PATH, body=req_body)
    self.assertEqual(actual, {'a': 1})
    fetch_args, fetch_kwargs = self.urlfetch_fetch.call_args
    self.assertEqual(fetch_args[0], URL)
    self.assertEqual(json.loads(fetch_kwargs.get('payload')), req_body)

  def test_not_found(self):
    client = GoogleSourceServiceClient(HOSTNAME)
    result = client._fetch(PATH)
    self.assertIsNone(result)

  def test_auth_failure(self):
    self.urlfetch_fetch.return_value.status_code = httplib.FORBIDDEN
    client = GoogleSourceServiceClient(HOSTNAME)
    with self.assertRaises(AuthenticationError):
      client._fetch(PATH)

  def test_bad_prefix(self):
    self.urlfetch_fetch.return_value.content = 'abc'
    self.urlfetch_fetch.return_value.status_code = httplib.OK
    client = GoogleSourceServiceClient(HOSTNAME)
    with self.assertRaises(Error):
      client._fetch(PATH)