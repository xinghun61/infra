# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging

from google.appengine.api import users
import jinja2
import webapp2

from common import constants
from gae_libs.http import auth_util


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(constants.HTML_TEMPLATE_DIR),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def ToJson(data):
  return json.dumps(data, sort_keys=True)  # Sort by key to keep order on UI.


JINJA_ENVIRONMENT.filters['tojson'] = ToJson


class Permission(object):
  ADMIN = 0
  CORP_USER = 8
  ANYONE = 16


class BaseHandler(webapp2.RequestHandler):
  # By default, set permission level to ADMIN only.
  # Subclass needs to overwrite it explicitly to give wider access.
  PERMISSION_LEVEL = Permission.ADMIN

  # By default, redirect to destination page after login for GET requests.
  LOGIN_REDIRECT_TO_DISTINATION_PAGE_FOR_GET = True

  def _HasPermission(self):
    if (self.request.headers.get('X-AppEngine-QueueName') or
        self.request.headers.get('X-AppEngine-Cron')):
      # Requests from task queues or cron jobs could access all HTTP endpoints.
      return True
    elif self.PERMISSION_LEVEL == Permission.ANYONE:
      return True
    elif self.PERMISSION_LEVEL == Permission.CORP_USER:
      # Only give access to google accounts or admins.
      return self.IsCorpUserOrAdmin()
    elif self.PERMISSION_LEVEL == Permission.ADMIN:
      return auth_util.IsCurrentUserAdmin()
    else:
      logging.error('Unknown permission level: %s' % self.PERMISSION_LEVEL)
      return False

  def IsCorpUserOrAdmin(self):
    """Returns True if the user logged in with corp account or as admin."""
    user_email = auth_util.GetUserEmail()
    return ((user_email and user_email.endswith('@google.com')) or
            auth_util.IsCurrentUserAdmin())

  def _ShowDebugInfo(self):
    # Show debug info only if the app is run locally during development, if the
    # currently logged-in user is an admin, or if it is explicitly requested
    # with parameter 'debug=1'.
    return users.is_current_user_admin() or self.request.get('debug') == '1'

  @staticmethod
  def CreateError(error_message, return_code=500):
    logging.error('Error occurred: %s', error_message)
    return {
        'template': 'error.html',
        'data': {'error_message': error_message},
        'return_code': return_code,
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

  def _SendResponse(self, template, data, return_code, cache_expiry=None):
    """Sends the response to the client in json or html as requested.

    Args:
      template: the template file to use.
      data: the data to feed the template or as the response if no template.
      return_code: the http status code for the response.
      cache_expiry: (optional) max-age for public cache-control in seconds.
    """
    self.response.clear()
    self.response.set_status(return_code)

    # Default format is html.
    response_format = self.request.get('format', 'html').lower()
    pretty_format = self.request.get('pretty')

    def _DumpJson(data):
      if not pretty_format:
        return json.dumps(data)

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
      return json.dumps(ordered_data, indent=2)

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
    self.response.headers['Content-Type'] = content_type
    self.response.write(data)

  def GetLoginUrl(self):
    """Returns the login url."""
    # For GET, all parameters are included in the URL. So it is safe to redirect
    # to the destination page. However, for POST, the parameters could be in the
    # body and include files, so it is better to redirect to the original page.
    if (self.request.method == 'GET' and
        self.LOGIN_REDIRECT_TO_DISTINATION_PAGE_FOR_GET):
      return users.create_login_url(self.request.url)
    else:
      return users.create_login_url(self.request.referrer)

  def _Handle(self, handler_func):
    try:
      if not self._HasPermission():
        template = 'error.html'
        data = {
            'error_message':
                ('Either not login or no permission. '
                 'Please login with your google.com account.'),
            'login_url': self.GetLoginUrl(),
        }
        return_code = 401
        cache_expiry = None
      else:
        result = handler_func()
        if result is None:
          return

        template = result.get('template', None)
        data = result.get('data', {})
        return_code = result.get('return_code', 200)
        cache_expiry = result.get('cache_expiry', None)
    except Exception as e:
      logging.exception(e)

      template = 'error.html'
      data = {
          'error_message': 'An internal error occurred.'
      }
      return_code = 500
      cache_expiry = None

    self._SendResponse(template, data, return_code, cache_expiry)

  def get(self):
    self._Handle(self.HandleGet)

  def post(self):
    self._Handle(self.HandlePost)
