# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import re
import urllib

import webapp2
import webtest

from google.appengine.api import users

from testing_utils import testing

from gae_libs.handlers import base_handler
from gae_libs.handlers.base_handler import BaseHandler, Permission


class PermissionLevelHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    pass


class PermissionTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/permission', PermissionLevelHandler),
      ], debug=True)

  def _VerifyUnauthorizedAccess(self, mocked_user_email=None, is_admin=False):
    if mocked_user_email:
      self.mock_current_user(user_email=mocked_user_email, is_admin=is_admin)
    response = self.test_app.get('/permission?format=json', status=401)
    self.assertEqual(('Either not log in yet or no permission. '
                      'Please log in with your @google.com account.'),
                     response.json_body.get('error_message'))

  def _VerifyAuthorizedAccess(self,
                              mocked_user_email=None,
                              is_admin=False,
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

  def testAccessForAppSelf(self):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.APP_SELF

    # No login.
    self._VerifyUnauthorizedAccess()

    # Non-admin has no access.
    self._VerifyUnauthorizedAccess('test@gmail.com')
    self._VerifyUnauthorizedAccess('test@chromium.org')
    self._VerifyUnauthorizedAccess('test@google.com')

    # Admin still has no access.
    self._VerifyUnauthorizedAccess('test@chromium.org', True)

    # Task queues and Cron jobs have access.
    for headers in [{
        'X-AppEngine-QueueName': 'task_queue'
    }, {
        'X-AppEngine-Cron': 'cron_job'
    }]:
      self._VerifyAuthorizedAccess(None, False, headers)

  def testUnknownPermissionLevel(self):
    PermissionLevelHandler.PERMISSION_LEVEL = 80000  # An unknown permission.
    self._VerifyUnauthorizedAccess('test@google.com')

  @mock.patch.object(users, 'is_current_user_admin', return_value=True)
  def testShowDebugInfoForAdmin(self, _):
    self.assertTrue(BaseHandler()._ShowDebugInfo())

  @mock.patch.object(users, 'is_current_user_admin', return_value=False)
  def testShowDebugInfoForNonAdmin(self, _):
    handler = BaseHandler()
    handler.request = {}
    self.assertFalse(handler._ShowDebugInfo())

  @mock.patch.object(users, 'is_current_user_admin', return_value=False)
  def testShowDebugInfoWithDebugFlag(self, _):
    handler = BaseHandler()
    handler.request = {'debug': '1'}
    self.assertTrue(handler._ShowDebugInfo())

  @mock.patch('gae_libs.appengine_util.IsInGAE')
  def testUserInfoWhenLogin(self, mocked_IsInGAE):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    mocked_IsInGAE.side_effect = [True]
    self.mock_current_user(user_email='test@chromium.org')
    response = self.test_app.get('/permission?format=json')
    self.assertEquals(200, response.status_int)

    user_info = response.json_body.get('user_info', {})
    self.assertEqual('test@chromium.org', user_info['email'])
    self.assertFalse(user_info['is_admin'])
    self.assertIsNotNone(user_info['logout_url'])
    self.assertTrue('login_url' not in user_info)

  @mock.patch('gae_libs.appengine_util.IsInGAE')
  @mock.patch('gae_libs.http.auth_util.GetUserEmail')
  def testUserInfoWhenNotLogin(self, mocked_GetUserEmail, mocked_IsInGAE):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    mocked_IsInGAE.side_effect = [True]
    mocked_GetUserEmail.side_effect = [None]
    response = self.test_app.get('/permission?format=json')
    self.assertEquals(200, response.status_int)

    user_info = response.json_body.get('user_info', {})
    self.assertIsNone(user_info['email'])
    self.assertFalse(user_info['is_admin'])
    self.assertTrue('logout_url' not in user_info)
    self.assertIsNotNone(user_info['login_url'])
    self.assertIsNone(response.json_body.get('xsrf_token'))

  @mock.patch('gae_libs.appengine_util.IsInGAE')
  def testAutoAddXsrfTokenWhenLogin(self, mocked_IsInGAE):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    mocked_IsInGAE.side_effect = [True]
    self.mock_current_user(user_email='test@chromium.org')
    response = self.test_app.get('/permission?format=json')
    self.assertEquals(200, response.status_int)

    self.assertIsNotNone(response.json_body['xsrf_token'])

  @mock.patch.object(
      PermissionLevelHandler,
      'HandleGet',
      return_value={'data': {
          'xsrf_token': 'abc'
      }})
  @mock.patch('gae_libs.appengine_util.IsInGAE')
  def testNotOverwriteAddXsrfTokenWhenLogin(self, mocked_IsInGAE, _):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    mocked_IsInGAE.side_effect = [True]
    self.mock_current_user(user_email='test@chromium.org')
    response = self.test_app.get('/permission?format=json')
    self.assertEquals(200, response.status_int)

    self.assertEqual('abc', response.json_body['xsrf_token'])

  @mock.patch('gae_libs.appengine_util.IsInGAE')
  def testNotIncludeUserEmail(self, mocked_IsInGAE):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    mocked_IsInGAE.side_effect = [False]
    self.mock_current_user(user_email='test@google.com')
    response = self.test_app.get('/permission?format=json')
    self.assertEquals(200, response.status_int)
    self.assertEquals({}, response.json_body)

  @mock.patch('gae_libs.appengine_util.IsInGAE')
  def testNotIncludeUserInfoForConciseResponse(self, mocked_IsInGAE):
    PermissionLevelHandler.PERMISSION_LEVEL = Permission.ANYONE
    mocked_IsInGAE.side_effect = [True]
    self.mock_current_user(user_email='test@google.com')
    response = self.test_app.get('/permission?format=json&concise=1')
    self.assertEquals(200, response.status_int)
    self.assertEquals({}, response.json_body)


class UnImplementedHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE


class UnimplementedGetAndPostTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
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
  app_module = webapp2.WSGIApplication(
      [
          ('/result', SetResultHandler),
      ], debug=True)

  def testNoResult(self):
    SetResultHandler.RESULT = None
    response = self.test_app.get('/result?format=json')
    self.assertEquals(200, response.status_int)
    self.assertEquals({}, response.json_body)

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

  def testAllowOrigin(self):
    SetResultHandler.RESULT = {'allowed_origin': '*'}
    response = self.test_app.get('/result')
    self.assertEquals(200, response.status_int)
    self.assertIn('Access-Control-Allow-Origin', response.headers)
    self.assertEquals('*', response.headers['Access-Control-Allow-Origin'])
    self.assertIn('Access-Control-Allow-Headers', response.headers)
    self.assertEquals('Origin, Authorization, Content-Type, Accept',
                      response.headers['Access-Control-Allow-Headers'])
    self.assertIn('Access-Control-Allow-Methods', response.headers)
    self.assertEquals('GET', response.headers['Access-Control-Allow-Methods'])


class RedirectHandler(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandlePost(self):
    return self.CreateRedirect('/url')


class RedirectTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/redirect', RedirectHandler),
      ], debug=True)

  def testRedirect(self):
    response = self.test_app.post('/redirect', status=302)
    self.assertTrue(response.headers.get('Location', '').endswith('/url'))


class ResultFormatTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/format', SetResultHandler),
      ], debug=True)

  def testDefaultFormatIsHtml(self):
    SetResultHandler.RESULT = {'data': 'error'}
    response = self.test_app.get('/format')
    self.assertEquals(200, response.status_int)
    self.assertEquals('text/html', response.content_type)
    self.assertEquals('error', response.body)

  def testRequestForHtmlFormat(self):
    SetResultHandler.RESULT = {
        'template': 'error.html',
        'data': {
            'error_message': 'error_message_here'
        }
    }
    response = self.test_app.get('/format?format=HTML')
    self.assertEquals(200, response.status_int)
    self.assertEquals('text/html', response.content_type)
    self.assertTrue('error_message_here' in response.body)

  def testRequestForJsonFormat(self):
    SetResultHandler.RESULT = {
        'template': 'error.html',
        'data': {
            'error_message': 'error'
        }
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
        'data': {
            'z': [1, 2, 3],
            'a': 'b',
            'b': '1' * 200
        }
    }
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
  app_module = webapp2.WSGIApplication(
      [
          ('/exception', InternalExceptionHandler),
      ], debug=True)

  @mock.patch('logging.exception')
  def testNormalInternalException(self, mocked_log_exception):
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*500 Internal Server Error.*An internal error occurred.*',
                   re.MULTILINE | re.DOTALL), self.test_app.get, '/exception')
    mocked_log_exception.assert_called_once()

  @mock.patch('logging.exception')
  def testSecurityScanInternalException(self, mocked_log_exception):
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*500 Internal Server Error.*An internal error occurred.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.get,
        '/exception',
        headers={'user-agent': '...GoogleSecurityScanner...'})
    self.assertFalse(mocked_log_exception.called)
