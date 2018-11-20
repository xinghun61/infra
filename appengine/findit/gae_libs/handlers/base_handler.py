# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging

import jinja2
import webapp2

from common import constants
from gae_libs import appengine_util
from gae_libs import token
from gae_libs.http import auth_util

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(constants.HTML_TEMPLATE_DIR),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def ToJson(data):
  # Sort by key to keep order on UI.
  # Use default str so it can serialize datetimes.
  return json.dumps(data, sort_keys=True, default=str)


JINJA_ENVIRONMENT.filters['tojson'] = ToJson


class Permission(object):
  APP_SELF = 0x1
  ADMIN = 0x10
  CORP_USER = 0x20
  ANYONE = 0x40


class BaseHandler(webapp2.RequestHandler):
  # By default, set permission level to ADMIN only.
  # Subclass needs to overwrite it explicitly to give wider access.
  PERMISSION_LEVEL = Permission.ADMIN

  def IsRequestFromAppSelf(self):
    """Returns True if the request is from the app itself."""
    # Requests from task queues or cron jobs are from app itself.
    return (self.request.headers.get('X-AppEngine-QueueName') or
            self.request.headers.get('X-AppEngine-Cron'))

  def IsCorpUserOrAdmin(self):
    """Returns True if the user logged in with corp account or as admin."""
    user_email = auth_util.GetUserEmail()
    return ((user_email and user_email.endswith('@google.com')) or
            auth_util.IsCurrentUserAdmin())

  def _HasPermission(self):
    if self.PERMISSION_LEVEL == Permission.ANYONE:
      # For public info, it is readable to the world.
      return True
    elif self.PERMISSION_LEVEL == Permission.CORP_USER:
      # Only give access to google accounts or admins.
      return self.IsCorpUserOrAdmin()
    elif self.PERMISSION_LEVEL == Permission.ADMIN:
      return auth_util.IsCurrentUserAdmin()
    elif self.PERMISSION_LEVEL == Permission.APP_SELF:
      # For internal endpoints for task queues and cron jobs, they are
      # accessible to the app itself only.
      return self.IsRequestFromAppSelf()
    else:
      logging.error('Unknown permission level: %s' % self.PERMISSION_LEVEL)
      return False

  def _ShowDebugInfo(self):
    # Show debug info only if the app is run locally during development, if the
    # currently logged-in user is an admin, or if it is explicitly requested
    # with parameter 'debug=1'.
    return auth_util.IsCurrentUserAdmin() or self.request.get('debug') == '1'

  @staticmethod
  def CreateError(error_message, return_code=500):
    logging.error('Error occurred: %s', error_message)
    return {
        'template': 'error.html',
        'data': {
            'error_message': error_message
        },
        'return_code': return_code,
    }

  @staticmethod
  def CreateRedirect(url):
    return {
        'redirect_url': url,
    }

  def HandleGet(self):  # pylint: disable=R0201
    """Handles a GET request.

    Returns:
      If overridden, return the following dict (all are optional):
      {
        'template': file name of the template,
        'data': data to feed the template or as the response if no template,
        'return_code': the HTTP status code for the response,
        'cache_expiry': how many seconds to set for cache control,
        'allowed_origin': a string representing the origin that the response can
                          be shared with, and the value is exactly one of '*',
                          '<origin>' and None.
      }
      If None or empty dict is returned, the overriding method should send the
      response to the client by itself.
    """
    return BaseHandler.CreateError('Not implemented yet!', 501)

  def HandlePost(self):  # pylint: disable=R0201
    """Handles a POST request.

    Returns:
      Same as HandleGet above.
    """
    return BaseHandler.CreateError('Not implemented yet!', 501)

  def _SendResponse(self,
                    template,
                    data,
                    return_code,
                    cache_expiry=None,
                    allowed_origin=None):
    """Sends the response to the client in json or html as requested.

    Args:
      template: the template file to use.
      data: the data to feed the template or as the response if no template.
      return_code: the http status code for the response.
      cache_expiry: (optional) max-age for public cache-control in seconds.
      allowed_origin: a string representing the origin that the response can
                      be shared with, and the value is exactly one of '*',
                      '<origin>' and None.
    """
    self.response.clear()
    self.response.set_status(return_code)

    # Default format is html.
    response_format = self.request.get('format', 'html').lower()
    pretty_format = self.request.get('pretty')

    def _DumpJson(data):
      if not pretty_format:
        return json.dumps(data, default=str)

      def _Compare(key, value):
        length_value = 1
        if isinstance(value, (list, dict)):
          length_value = 2 + len(value)
        if isinstance(value, (str, basestring)) and len(value) > 100:
          length_value = 10 + len(value)
        return (length_value, key)

      # Order the dictionary so that simple and small data comes first.
      ordered_data = collections.OrderedDict(
          sorted(data.iteritems(), key=lambda (k, v): _Compare(k, v)))
      return json.dumps(ordered_data, indent=2, default=str)

    if response_format == 'html' and template is not None:
      content_type = 'text/html'
      data = JINJA_ENVIRONMENT.get_template(template).render(data)
    elif response_format == 'json':
      content_type = 'application/json'
      data = _DumpJson(data)
    elif isinstance(data, (list, dict)):
      content_type = 'application/json'
      data = _DumpJson(data)
    else:
      content_type = 'text/html'

    if cache_expiry is not None:
      self.response.headers['cache-control'] = (
          'max-age=%s, public' % cache_expiry)

    if allowed_origin:
      self.response.headers['Access-Control-Allow-Origin'] = allowed_origin
      self.response.headers['Access-Control-Allow-Methods'] = 'GET'
      self.response.headers['Access-Control-Allow-Headers'] = (
          'Origin, Authorization, Content-Type, Accept')

    self.response.headers['Content-Type'] = content_type
    # Set X-Frame-Options to prevent Clickjacking.
    self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    self.response.write(data)

  def _Handle(self, handler_func):
    try:
      if not self._HasPermission():
        logging.info('Current user has no permission to access the endpoint.')
        template = 'error.html'
        data = {
            'error_message': ('Either not log in yet or no permission. '
                              'Please log in with your @google.com account.'),
        }
        return_code = 401
        redirect_url = None
        cache_expiry = None
        allowed_origin = None
      else:
        result = handler_func() or {}
        redirect_url = result.get('redirect_url')

        template = result.get('template', None)
        data = result.get('data', {})
        return_code = result.get('return_code', 200)
        cache_expiry = result.get('cache_expiry', None)
        allowed_origin = result.get('allowed_origin', None)

    except Exception as e:
      user_agent = self.request.headers.get('user-agent')
      if not (user_agent and 'GoogleSecurityScanner' in user_agent):
        logging.exception(e)

      template = 'error.html'
      data = {'error_message': 'An internal error occurred.'}
      return_code = 500
      redirect_url = None
      cache_expiry = None
      allowed_origin = None

    if redirect_url is not None:
      self.response.clear()
      self.redirect(redirect_url)
      return

    # Not add user login/logout info in unit tests environment to avoid updating
    # too many existing testcases.
    if (not appengine_util.IsInUnitTestEnvironment() and
        not self.request.get('concise') == '1'):
      data['user_info'] = auth_util.GetUserInfo(self.request.url)
      # If not yet, generate one xsrf token for the login user.
      if not data.get('xsrf_token') and data.get('user_info', {}).get('email'):
        data['xsrf_token'] = token.GenerateAuthToken(
            'site',
            data.get('user_info', {}).get('email'))

    self._SendResponse(template, data, return_code, cache_expiry,
                       allowed_origin)

  def get(self):
    self._Handle(self.HandleGet)

  def post(self):
    self._Handle(self.HandlePost)
