# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import urlparse

from common.codereview import CodeReview
from common.http_client_appengine import HttpClientAppengine


_RIETVELD_ISSUE_NUMBER_RE = re.compile('^/(\d+)/?.*')


class Rietveld(CodeReview):
  """The implementation of CodeReview interface for Rietveld."""
  HTTP_CLIENT = HttpClientAppengine()

  def _GetXsrfToken(self, rietveld_url):
    """Returns the xsrf token for follow-up requests."""
    headers = {
        'X-Requesting-XSRF-Token': '1',
        'Accept': 'text/plain',
    }
    url = '%s/xsrf_token' % rietveld_url
    status_code, xsrf_token = self.HTTP_CLIENT.Post(
        url, data=None, headers=headers)
    if status_code != 200:
      logging.error('Failed to get xsrf token from %s', rietveld_url)
      xsrf_token = None
    return xsrf_token

  def _GetRietveldUrlAndIssueNumber(self, issue_url):
    """Parses the given Rietveld issue url.

    Args:
      issue_url(str): The url to an issue on Rietveld.
    Returns:
      (rietveld_url, issue_number)
      rietveld_url(str): The root url of the Rietveld app.
      issue_number(str): The issue number.
    """
    u = urlparse.urlparse(issue_url)
    rietveld_url = 'https://%s' % u.netloc  # Enforces https.
    issue_number = _RIETVELD_ISSUE_NUMBER_RE.match(u.path).group(1)
    return rietveld_url, issue_number

  def _EncodeMultipartFormData(self, fields):
    """Encodes form fields for multipart/form-data"""
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

  def PostMessage(self, issue_url, message):
    rietveld_url, issue_number = self._GetRietveldUrlAndIssueNumber(issue_url)
    url = '%s/%s/publish' % (rietveld_url, issue_number)
    xsrf_token = self._GetXsrfToken(rietveld_url)
    if not xsrf_token:
      return False
    form_fields = {
        'xsrf_token': xsrf_token,
        'message': message,
        'message_only': 'True',
        'add_as_reviewer': 'False',
        'send_mail': 'True',
        'no_redirect': 'True',
    }
    content_type, body = self._EncodeMultipartFormData(form_fields)
    headers = {
        'Content-Type': content_type,
        'Accept': 'text/plain',
    }
    status_code, content = self.HTTP_CLIENT.Post(
        url, data=body, headers=headers)
    return status_code == 200 and content == 'OK'
