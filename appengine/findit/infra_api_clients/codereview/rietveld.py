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

import json
import logging
import re
import urlparse

from common.findit_http_client import FinditHttpClient
from libs import time_util
from infra_api_clients.codereview import cl_info
from infra_api_clients.codereview import codereview

_RIETVELD_ISSUE_NUMBER_RE = re.compile('^/(\d+)/?.*')
_PATCHSET_REVERTED_TO_ISSUE_REGEX = re.compile(
    r'A revert of this CL \(patchset #\d+ id:\d+\) has been '
    r'created in (?P<issueurl>.*) by .*'
    r'.\n\nThe reason for reverting is: .*')
_PATCHSET_TO_REVISION_REGEX = re.compile(
    r'Committed patchset #\d+ \(id:\d+\) as '
    r'https://.*/(?P<revision>[a-f\d]{40})')
_PATCHSET_TO_REVISION_MANUAL_REGEX = re.compile(
    r'Committed patchset #\d+ \(id:\d+\) manually as '
    r'(?P<revision>[a-f\d]{40})(?:\.$| .*)')
# NB: We capture the email as any non-space characters after 'by' to avoid
# matching in case the email is followed by ` to run a CQ dry run`
_COMMIT_ATTEMPT_REGEX = re.compile(r'^The CQ bit was checked by [^ ]+$')


class Rietveld(codereview.CodeReview):
  """The implementation of CodeReview interface for Rietveld."""
  HTTP_CLIENT = FinditHttpClient(follow_redirects=False)

  def __init__(self, server_hostname):
    super(Rietveld, self).__init__(server_hostname)

  def GetCodeReviewUrl(self, change_id):
    return 'https://%s/%s/' % (self._server_hostname, change_id)

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

  def PostMessage(self, change_id, message, should_email=True):
    url_path = '/%s/publish' % change_id
    form_fields = {
        'message': message,
        'message_only': 'True',
        'add_as_reviewer': 'False',
        'send_mail': str(bool(should_email)),
        'no_redirect': 'True',
    }
    status_code, content = self._SendPostRequest(url_path, form_fields)
    return status_code == 200 and content == 'OK'

  # Signature differs. Make patchset id required here - pylint: disable=W0222
  def CreateRevert(self, reason, change_id, patchset_id):
    url_path = '/api/%s/%s/revert' % (change_id, patchset_id)
    form_fields = {
        'revert_reason': reason,
        'no_redirect': 'True',
        'revert_cq': 0,  # Explicitly set it to 0 to avoid automatic CQ.
    }
    status_code, content = self._SendPostRequest(url_path, form_fields)
    if status_code == 200:
      return content
    else:
      logging.error('Failed to create a revert for %s/%s on Rietveld: %s',
                    change_id, patchset_id, content)
      return None

  def _ParseClInfo(self, data, cl):

    def patchset_to_revision_func(cl, message):
      matches_cq = _PATCHSET_TO_REVISION_REGEX.match(message['text'])
      matches_manual = _PATCHSET_TO_REVISION_MANUAL_REGEX.match(message['text'])
      matches_any = matches_cq or matches_manual
      if not matches_any:
        return
      patchset_id = str(message.get('patchset'))
      revision = matches_any.group('revision')
      timestamp = time_util.DatetimeFromString(message['date'])
      commit = cl_info.Commit(patchset_id, revision, timestamp)
      cl.commits.append(commit)
      if matches_manual:
        committer = message['sender']
        # When a patch is manually landed, there is no cq attempt, but since
        # we care about when action was taken, we take the timing of the commit
        # itself as the commit attempt timestamp.
        cl.AddCqAttempt(patchset_id, committer, timestamp)

    def patchset_reverted_to_issue_func(cl, message):
      matches = _PATCHSET_REVERTED_TO_ISSUE_REGEX.match(message['text'])
      if not matches:
        return
      patchset_id = str(message['patchset'])
      issue_url = matches.group('issueurl')
      url_parts = issue_url.split('/')
      # Support both https://host/1234 and https://host/1234/
      change_id = url_parts[-1] or url_parts[-2]
      reverter = message['sender']
      timestamp = time_util.DatetimeFromString(message['date'])
      revert_cl = self.GetClDetails(change_id)
      revert = cl_info.Revert(patchset_id, revert_cl, reverter, timestamp)
      cl.reverts.append(revert)

    def commit_attempt_func(cl, message):
      matches = _COMMIT_ATTEMPT_REGEX.match(message['text'])
      if not matches:
        return
      timestamp = time_util.DatetimeFromString(message['date'])
      committer = message['sender']
      patchset_id = str(message['patchset'])
      cl.AddCqAttempt(patchset_id, committer, timestamp)

    details_funcs = [
        patchset_to_revision_func,
        patchset_reverted_to_issue_func,
        commit_attempt_func,
    ]

    # Sort by timestamp
    messages = sorted(
        data['messages'],
        key=lambda x: time_util.DatetimeFromString(x.get('date')))
    for message in messages:
      for f in details_funcs:
        f(cl, message)
    cl.closed = data['closed']
    cl.cc = data['cc']
    cl.reviewers = data['reviewers']
    cl.auto_revert_off = codereview.IsAutoRevertOff(data['description'])
    cl.owner_email = data['owner_email']
    return cl

  def GetClDetails(self, change_id):
    params = {'messages': 'true'}
    url = 'https://%s/api/%s' % (self._server_hostname, change_id)
    status_code, content = self.HTTP_CLIENT.Get(url, params=params)
    if status_code == 200:  # pragma: no branch
      return self._ParseClInfo(
          json.loads(content), cl_info.ClInfo(self._server_hostname, change_id))
    return None  # pragma: no cover

  def AddReviewers(self, change_id, reviewers, message=None):
    cl = self.GetClDetails(change_id)
    current_cc_list = cl.cc
    new_reviewers = set(cl.reviewers) | set(reviewers)

    url_path = '/%s/publish' % change_id
    form_fields = {
        'message_only': 'False',
        # this flag is used when the recipient of the message is to be added
        # as reviewer.
        'add_as_reviewer': 'False',
        'send_mail': 'True',
        'no_redirect': 'True',
        'commit': 'False',
        'reviewers': ','.join(list(new_reviewers)),
        'cc': ','.join(current_cc_list),
        'message': message or '',
    }

    status_code, content = self._SendPostRequest(url_path, form_fields)
    return status_code == 200 and content == 'OK'

  def GetChangeIdForReview(self, review_url):  # pragma: no cover
    u = urlparse.urlparse(review_url)
    return u.path.split('/')[-1]

  def SubmitRevert(self, _):
    logging.error('Should not auto submit rietveld reverts.')
