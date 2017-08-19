# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""This file defines a subclass of Servlet for JSON feeds.

A "feed" is a servlet that is accessed by another part of our system and that
responds with a JSON value rather than HTML to display in a browser.
"""

import httplib
import json
import logging

from google.appengine.api import app_identity

import settings

from framework import framework_constants
from framework import permissions
from framework import servlet
from framework import xsrf
from search import query2ast

# This causes a JS error for a hacker trying to do a cross-site inclusion.
XSSI_PREFIX = ")]}'\n"


class JsonFeed(servlet.Servlet):
  """A convenient base class for JSON feeds."""

  # By default, JSON output is compact.  Subclasses can set this to
  # an integer, like 4, for pretty-printed output.
  JSON_INDENT = None

  # Some JSON handlers can only be accessed from our own app.
  CHECK_SAME_APP = False

  def HandleRequest(self, _mr):
    """Override this method to implement handling of the request.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      A dictionary of json data.
    """
    raise servlet.MethodNotSupportedError()

  def _DoRequestHandling(self, request, mr):
    """Do permission checking, page processing, and response formatting."""
    try:
      if self.CHECK_SECURITY_TOKEN and mr.auth.user_id:
        # Validate the XSRF token with the specific request path for this
        # servlet.  But, not every XHR request has a distinct token, so just
        # use 'xhr' for ones that don't.
        # TODO(jrobbins): make specific tokens for:
        # user and project stars, issue options, check names.
        try:
          logging.info('request in jsonfeed is %r', request)
          xsrf.ValidateToken(mr.token, mr.auth.user_id, request.path)
        except xsrf.TokenIncorrect:
          logging.info('using token path "xhr"')
          xsrf.ValidateToken(mr.token, mr.auth.user_id, xsrf.XHR_SERVLET_PATH)

      if self.CHECK_SAME_APP and not settings.dev_mode:
        calling_app_id = request.headers.get('X-Appengine-Inbound-Appid')
        if calling_app_id != app_identity.get_application_id():
          self.response.status = httplib.FORBIDDEN
          return

      self._CheckForMovedProject(mr, request)
      self.AssertBasePermission(mr)

      json_data = self.HandleRequest(mr)

      self._RenderJsonResponse(json_data)

    except query2ast.InvalidQueryError as e:
      logging.warning('Trapped InvalidQueryError: %s', e)
      logging.exception(e)
      msg = e.message if e.message else 'invalid query'
      self.abort(400, msg)
    except permissions.PermissionException as e:
      logging.info('Trapped PermissionException %s', e)
      self.response.status = httplib.FORBIDDEN

  # pylint: disable=unused-argument
  # pylint: disable=arguments-differ
  # Note: unused arguments necessary because they are specified in
  # registerpages.py as an extra URL validation step even though we
  # do our own URL parsing in monorailrequest.py
  def get(self, project_name=None, viewed_username=None, hotlist_id=None):
    """Collect page-specific and generic info, then render the page.

    Args:
      project_name: string project name parsed from the URL by webapp2,
        but we also parse it out in our code.
      viewed_username: string user email parsed from the URL by webapp2,
        but we also parse it out in our code.
      hotlist_id: string hotlist id parsed from the URL by webapp2,
        but we also parse it out in our code.
    """
    self._DoRequestHandling(self.mr.request, self.mr)

  # pylint: disable=unused-argument
  # pylint: disable=arguments-differ
  def post(self, project_name=None, viewed_username=None, hotlist_id=None):
    """Parse the request, check base perms, and call form-specific code."""
    self._DoRequestHandling(self.mr.request, self.mr)

  def _RenderJsonResponse(self, json_data):
    """Serialize the data as JSON so that it can be sent to the browser."""
    json_str = json.dumps(json_data, indent=self.JSON_INDENT)
    logging.debug(
      'Sending JSON response: %r length: %r',
      json_str[:framework_constants.LOGGING_MAX_LENGTH], len(json_str))
    self.response.content_type = framework_constants.CONTENT_TYPE_JSON
    self.response.write(XSSI_PREFIX)
    self.response.write(json_str)


class InternalTask(JsonFeed):
  """Internal tasks are JSON feeds that can only be reached by our own code."""

  CHECK_SECURITY_TOKEN = False
