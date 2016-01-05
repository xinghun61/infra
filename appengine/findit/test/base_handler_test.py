# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import urllib

import webapp2
import webtest

from testing_utils import testing

import base_handler
from base_handler import BaseHandler
from base_handler import Permission


class PermissionLevelHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    pass


class PermissionTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/permission', PermissionLevelHandler),
  ], debug=True)

  def _VerifyUnauthorizedAccess(self, mocked_user_email=None):
    if mocked_user_email:
      self.mock_current_user(user_email=mocked_user_email)
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*Either not login or no permission.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, '/permission')

  def _VerifyAuthorizedAccess(self, mocked_user_email=None, is_admin=False,
                              headers=None):
    if mocked_user_email:
      self.mock_current_user(user_email=mocked_user_email, is_admin=is_admin)
    if headers:
      response = self.test_app.get('/permission', headers=headers)
    else:
      response = self.test_app.get('/permission')
    self.assertEquals(200, response.status_int)

  def testAccessForAnyone(self):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    self._VerifyAuthorizedAccess()
    self._VerifyAuthorizedAccess('test@gmail.com')
    self._VerifyAuthorizedAccess('test@chromium.org')
    self._VerifyAuthorizedAccess('test@google.com')

  def testAccessForAdmin(self):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ADMIN

    # No login.
    self._VerifyUnauthorizedAccess()

    # Non-admin has no access.
    self._VerifyUnauthorizedAccess('test@gmail.com')
    self._VerifyUnauthorizedAccess('test@chromium.org')
    self._VerifyUnauthorizedAccess('test@google.com')

    # Admin has access.
    self._VerifyAuthorizedAccess('test@chromium.org', True)

  def testAccessForCorpUser(self):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.CORP_USER

    # Non-member has no access.
    self._VerifyUnauthorizedAccess('test@gmail.com')
    self._VerifyUnauthorizedAccess('test@chromium.org')

    # Corp users and admin has access.
    self._VerifyAuthorizedAccess('test@google.com')
    self._VerifyAuthorizedAccess('test@chromium.org', True)

  def testAccessByTaskQueue(self):
    for permission in (Permission.ANYONE, Permission.CORP_USER,
                       Permission.ADMIN):
      PermissionLevelHandler.PERMISSION_LEVEL = permission
      # Simulation of task queue request by setting the header requires admin
      # login.
      self._VerifyAuthorizedAccess(
          'test@chromium.org', True, {'X-AppEngine-QueueName': 'task_queue'})

  def testUnknownPermissionLevel(self):
    PermissionLevelHandler.PERMISSION_LEVEL = 80000  # An unknown permission.
    self._VerifyUnauthorizedAccess('test@google.com')

  def testLoginLinkWithReferer(self):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.CORP_USER
    referer_url = 'http://localhost/referer'
    login_url = ('https://www.google.com/accounts/Login?continue=%s' %
                 urllib.quote(referer_url))
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*%s.*' % re.escape(login_url),
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, '/permission', headers={'referer': referer_url})

  def testLoginLinkWithRequestedUrl(self):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.CORP_USER
    request_url = '/permission'
    login_url = ('https://www.google.com/accounts/Login?continue=%s' %
                 urllib.quote('http://localhost/permission'))
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*%s.*' % re.escape(login_url),
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, request_url)


class UnImplementedHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE


class UnimplementedGetAndPostTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/unimplemented', UnImplementedHandler),
  ], debug=True)

  def testUnimplementedGet(self):
    self.assertRaisesRegexp(webtest.app.AppError, '.*501 Not Implemented.*',
                            self.test_app.get, '/unimplemented')

  def testUnimplementedPost(self):
    self.assertRaisesRegexp(webtest.app.AppError, '.*501 Not Implemented.*',
                            self.test_app.post, '/unimplemented')


class SetResultHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  RESULT = None

  def HandleGet(self):
    return SetResultHandler.RESULT


class ResultTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/result', SetResultHandler),
  ], debug=True)

  def testNoResult(self):
    SetResultHandler.RESULT = None
    response = self.test_app.get('/result')
    self.assertEquals(200, response.status_int)
    self.assertEquals('text/html', response.content_type)
    self.assertEquals('', response.body)

  def testNoCacheControl(self):
    SetResultHandler.RESULT = {}
    response = self.test_app.get('/result')
    self.assertEquals(200, response.status_int)
    self.assertTrue(response.cache_control.no_cache)

  def testCacheControl(self):
    SetResultHandler.RESULT = {'cache_expiry': 5}
    response = self.test_app.get('/result')
    self.assertEquals(200, response.status_int)
    self.assertFalse(response.cache_control.no_cache)
    self.assertTrue(response.cache_control.public)
    self.assertEquals(5, response.cache_control.max_age)


class ResultFormatTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/format', SetResultHandler),
  ], debug=True)

  def testDefaultFormatIsHtml(self):
    SetResultHandler.RESULT = {
        'data': 'error'
    }
    response = self.test_app.get('/format')
    self.assertEquals(200, response.status_int)
    self.assertEquals('text/html', response.content_type)
    self.assertEquals('error', response.body)

  def testRequestForHtmlFormat(self):
    SetResultHandler.RESULT = {
        'template': 'error.html',
        'data': {'error_message': 'error_message_here'}
    }
    response = self.test_app.get('/format?format=HTML')
    self.assertEquals(200, response.status_int)
    self.assertEquals('text/html', response.content_type)
    self.assertTrue('error_message_here' in response.body)

  def testRequestForJsonFormat(self):
    SetResultHandler.RESULT = {
        'template': 'error.html',
        'data': {'error_message': 'error'}
    }
    response = self.test_app.get('/format?format=json')
    self.assertEquals(200, response.status_int)
    self.assertEquals('application/json', response.content_type)
    self.assertEquals(SetResultHandler.RESULT['data'], response.json_body)

  def testImplicitJsonFormat(self):
    def testResult(result):
      SetResultHandler.RESULT = result
      response = self.test_app.get('/format')
      self.assertEquals(200, response.status_int)
      self.assertEquals('application/json', response.content_type)
      self.assertEquals(result['data'], response.json_body)
    testResult({'data': {'a': 'b'}})
    testResult({'data': [1, 2]})

  def testPrettyJson(self):
    SetResultHandler.RESULT = {
        'data': {'z': [1, 2, 3], 'a': 'b', 'b': '1' * 200}}
    response = self.test_app.get('/format?format=json&pretty=1')
    self.assertEquals(200, response.status_int)
    self.assertEquals('application/json', response.content_type)
    expected_body = ('{\n  "a": "b", \n  "z": [\n    1, \n    2, \n    3\n  ], '
                     '\n  "b": "%s"\n}' % ('1' * 200))
    self.assertEquals(response.body, expected_body)

  def testToJson(self):
    self.assertEqual('{}', base_handler.ToJson({}))

class InternalExceptionHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    raise Exception('abc')


class InternalExceptionTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/exception', InternalExceptionHandler),
  ], debug=True)

  def testInternalException(self):
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*500 Internal Server Error.*An internal error occurred.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, '/exception')
