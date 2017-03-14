# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO: In the new layout, this should move to the ./services or
# ./services/waterfall_app directories, since it is only used by Waterfall.

# TODO: we ought to abstract over the HTTP_CLIENT member (which is only
# used by the Post method) by passing it to the constructor. That way
# things are more losely coupled, improving modularity and reducing
# fragility. In addition, for easier mocking, we may want to just have
# the thing passed for HTTP_CLIENT to be ``callable``, rather than giving
# a name to the method we use on that object.

import logging
import re
import urlparse

from infra_api_clients.codereview import codereview
from gae_libs.http.http_client_appengine import HttpClientAppengine


_RIETVELD_ISSUE_NUMBER_RE = re.compile('^/(\d+)/?.*')


class Rietveld(codereview.CodeReview):
  """The implementation of CodeReview interface for Rietveld."""
  HTTP_CLIENT = HttpClientAppengine(follow_redirects=False)

  def __init__(self, server_hostname):
    super(Rietveld, self).__init__(server_hostname)

  def _GetXsrfToken(self):
    """Returns the xsrf token for follow-up requests."""
    headers = {
        'X-Requesting-XSRF-Token': '1',
        'Accept': 'text/plain',
    }
    url = 'https://%s/xsrf_token' % self._server_hostname
    status_code, xsrf_token = self.HTTP_CLIENT.Post(
        url, data=None, headers=headers)
    if status_code != 200:
      logging.error('Failed to get xsrf token from %s', url)
      xsrf_token = None
    return xsrf_token

  def _EncodeMultipartFormData(self, fields):
    """Encodes form fields for multipart/form-data"""
    if not fields:
      return None, None
    BOUNDARY = '-F-I-N-D-I-T-M-E-S-S-A-G-E-'
    CRLF = '\r\n'
    lines = []
    for key, value in fields.iteritems():
      lines.append('--' + BOUNDARY)
      lines.append('Content-Disposition: form-data; name="%s"' % key)
      lines.append('')
      lines.append(str(value))
    lines.append('--' + BOUNDARY + '--')
    lines.append('')
    body = CRLF.join(lines)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body

  def _SendPostRequest(self, url_path, form_fields):
    """Sends a post request with xsrf if needed and returns the response.

    A xsrf token will be automatically added.

    Args:
      url_path (str): The url path to send the post reqeust to, eg:
          '/1234/publish'.
      form_fields (dict): A dict of the form fields for the post request.

    Returns:
      (status_code, content)
      status_code (int): The http status code of the response.
      content (str): The content of the response.
    """
    url = 'https://%s%s' % (self._server_hostname, url_path)
    form_fields = form_fields or {}
    xsrf_token = self._GetXsrfToken()
    if not xsrf_token:
      return 403, 'failed to get a xsrf token'
    form_fields['xsrf_token'] = xsrf_token
    headers = {
        'Accept': 'text/plain',
    }
    content_type, body = self._EncodeMultipartFormData(form_fields)
    headers['Content-Type'] = content_type
    return self.HTTP_CLIENT.Post(url, data=body, headers=headers)

  def PostMessage(self, change_id, message):
    url_path = '/%s/publish' % change_id
    form_fields = {
        'message': message,
        'message_only': 'True',
        'add_as_reviewer': 'False',
        'send_mail': 'True',
        'no_redirect': 'True',
    }
    status_code, content = self._SendPostRequest(url_path, form_fields)
    return status_code == 200 and content == 'OK'

  def CreateRevert(self, change_id, patchset_id=None):
    # TODO (stgao): implement the api on Rietveld.
    raise NotImplementedError()

  def AddReviewers(self, change_id, reviewers, message=None):
      raise NotImplementedError()  # pragma: no cover
