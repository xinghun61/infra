# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import webapp2

from handlers import url_redirect
from waterfall.test import wf_testcase

_REDIRECTION_MAPPING_MOCK = {
    'old.host.com': {
        'hostname': 'new.host.com',
        'url-mappings': {
            '/old/url1': '/new/url1',
        },
    },
    'stable.host.com': {
        'url-mappings': {
            '/old/url2': '/new/url2',
        },
    },
}


class URLRedirectTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      (r'/.*', url_redirect.URLRedirect),
  ],
                                       debug=True)

  @mock.patch.object(
      url_redirect.URLRedirect,
      '_GetHostAndPath',
      return_value=('old.host.com', '/old/url1'))
  @mock.patch.object(url_redirect, '_REDIRECTION_MAPPING',
                     _REDIRECTION_MAPPING_MOCK)
  def testRedirectToNewHostAndNewPath(self, *_):
    response = self.test_app.get('/old/url1')
    self.assertEqual(
        response.headers.get('Location', ''), 'https://new.host.com/new/url1')

  @mock.patch.object(
      url_redirect.URLRedirect,
      '_GetHostAndPath',
      return_value=('old.host.com', '/stable/url'))
  @mock.patch.object(url_redirect, '_REDIRECTION_MAPPING',
                     _REDIRECTION_MAPPING_MOCK)
  def testRedirectToNewHostAndStablePath(self, *_):
    response = self.test_app.get('/stable/url')
    self.assertEqual(
        response.headers.get('Location', ''), 'https://new.host.com/stable/url')

  @mock.patch.object(
      url_redirect.URLRedirect,
      '_GetHostAndPath',
      return_value=('stable.host.com', '/old/url2'))
  @mock.patch.object(url_redirect, '_REDIRECTION_MAPPING',
                     _REDIRECTION_MAPPING_MOCK)
  def testRedirectToNewPathOnly(self, *_):
    response = self.test_app.get('/old/url2?param=value')
    self.assertEqual(
        response.headers.get('Location', ''),
        'https://stable.host.com/new/url2?param=value')

  @mock.patch.object(
      url_redirect.URLRedirect,
      '_GetHostAndPath',
      return_value=('stable.host.com', '/url/not/exists'))
  @mock.patch.object(url_redirect, '_REDIRECTION_MAPPING',
                     _REDIRECTION_MAPPING_MOCK)
  def testRedirectForNotExistingUrl(self, *_):
    response = self.test_app.get('/url/not/exists?format=json', status=404)
    self.assertEqual(response.json_body.get('error_message'), 'Page not found')
