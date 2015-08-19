# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Yet another wrapper around Gerrit REST API."""

import base64
import cookielib
import functools
import json
import logging
import requests
import requests_cache
import time
import urllib

from requests.packages import urllib3


LOGGER = logging.getLogger(__name__)
NOTIFY_NONE = 'NONE'
NOTIFY_OWNER = 'OWNER'
NOTIFY_OWNER_REVIEWERS = 'OWNER_REVIEWERS'
NOTIFY_ALL = 'ALL'

def _not_read_only(f):
  @functools.wraps(f)
  def wrapper(self, *args, **kwargs):
    if self._read_only:
      raise AccessViolationException(
          'Method call of method not accessible for read_only Gerrit instance.')
    return f(self, *args, **kwargs)
  return wrapper


class AccessViolationException(Exception):
  """A method was called which would require write access to Gerrit."""

class UnexpectedResponseException(Exception):
  """Gerrit returned something unexpected."""

  def __init__(self, http_code, body):  # pragma: no cover
    super(UnexpectedResponseException, self).__init__()
    self.http_code = http_code
    self.body = body

  def __str__(self):  # pragma: no cover
    return 'Unexpected response (HTTP %d): %s' % (self.http_code, self.body)


class BlockCookiesPolicy(cookielib.DefaultCookiePolicy):
  def set_ok(self, cookie, request):
    return False # pragma: no cover


class Gerrit(object):
  """Wrapper around a single Gerrit host. Not thread-safe.

  Args:
    host (str): gerrit host name.
    creds (Credentials): provides credentials for the Gerrit host.
    throttle_delay_sec (int): minimal time delay between two requests, to
      avoid hammering the Gerrit server.
  """

  def __init__(self, host, creds, throttle_delay_sec=0, read_only=False):
    self._auth_header = 'Basic %s' % (
        base64.b64encode('%s:%s' % creds[host]))
    self._url_base = 'https://%s/a' % host.rstrip('/')
    self._throttle = throttle_delay_sec
    self._read_only = read_only
    self._last_call_ts = None
    self.session = requests.Session()
    # Do not use cookies with Gerrit. This breaks interaction with Google's
    # Gerrit instances. Do not use cookies as advised by the Gerrit team.
    self.session.cookies.set_policy(BlockCookiesPolicy())
    retry_config = urllib3.util.Retry(total=4, backoff_factor=2,
                                      status_forcelist=[500, 503])
    self.session.mount(self._url_base, requests.adapters.HTTPAdapter(
        max_retries=retry_config))

  def _sleep(self, time_since_last_call):
    time.sleep(self._throttle - time_since_last_call) # pragma: no cover

  def _request(self, method, request_path, params=None, body=None):
    """Sends HTTP request to Gerrit.

    Args:
      method: HTTP method (e.g 'GET', 'POST', ...).
      request_path: URL of the endpoint, relative to host (e.g. '/accounts/id').
      params: dict with query parameters.
      body: optional request body, will be serialized to JSON.

    Returns:
      Tuple (response code, deserialized JSON response).
    """
    if not request_path.startswith('/'):
      request_path = '/' + request_path

    full_url = '%s%s' % (self._url_base, request_path)

    # Wait to avoid Gerrit quota, don't wait if a response is in the cache.
    if self._throttle and not _is_response_cached(method, full_url):
      if self._last_call_ts:
        time_since_last_call = time.time() - self._last_call_ts
        if time_since_last_call < self._throttle:
          self._sleep(time_since_last_call)
      self._last_call_ts = time.time()

    headers = {
        # This makes the server return compact JSON.
        'Accept': 'application/json',
        # This means responses will be gzip compressed.
        'Accept-encoding': 'gzip',
        'Authorization': self._auth_header,
    }

    if body is not None:
      body = json.dumps(body)
      headers['Content-Type'] = 'application/json;charset=UTF-8'

    LOGGER.debug('%s %s', method, full_url)
    response = self.session.request(
        method=method,
        url=full_url,
        params=params,
        data=body,
        headers=headers)

    # Gerrit prepends )]}' to response.
    prefix = ')]}\'\n'
    body = response.text
    if body and body.startswith(prefix):
      body = json.loads(body[len(prefix):])

    return response.status_code, body

  def get_account(self, account_id):
    """Returns a dict describing a Gerrit account or None if no such account.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-accounts.html#get-account

    Args:
      account_id: email, numeric account id, or 'self'.

    Returns:
      None if no such account, AccountInfo dict otherwise.
    """
    assert '/' not in account_id
    code, body = self._request('GET', '/accounts/%s' % account_id)
    if code == 200:
      return body
    if code == 404:
      return None
    raise UnexpectedResponseException(code, body)

  @_not_read_only
  def add_group_members(self, group, members):
    """Adds a bunch of members to a group.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-groups.html#_add_group_members

    Args:
      group: name of a group to add members to.
      members: iterable with emails of accounts to add to the group.

    Returns:
      None

    Raises:
      UnexpectedResponseException: if call failed.
    """
    if '/' in group:
      raise ValueError('Invalid group name: %s' % group)
    code, body = self._request(
        method='POST',
        request_path='/groups/%s/members.add' % group,
        body={'members': list(members)})
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  def is_account_active(self, account_id): # pragma: no cover
    if '/' in account_id:
      raise ValueError('Invalid account id: %s' % account_id)
    code, body = self._request(
        method='GET',
        request_path='/accounts/%s/active' % account_id)
    if code == 200:
      return True
    if code == 204:
      return False
    raise UnexpectedResponseException(code, body)

  @_not_read_only
  def activate_account(self, account_id): # pragma: no cover
    """Sets account state to 'active'.

    Args:
      account_id (str): account to update.

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    if '/' in account_id:
      raise ValueError('Invalid account id: %s' % account_id)
    code, body = self._request(
        method='PUT',
        request_path='/accounts/%s/active' % account_id)
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)

  def get_projects(self, prefix=''): # pragma: no cover
    """Returns list of projects with names starting with a prefix.

    Args:
      prefix (str): optional project name prefix to limit the listing to.

    Returns:
      Dict <project name> -> {'state': 'ACTIVE', 'parent': 'All-Projects'}

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    code, body = self._request(
        method='GET',
        request_path='/projects/?p=%s&t' % urllib.quote(prefix, safe=''))
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)
    return body

  def get_project_parent(self, project): # pragma: no cover
    """Retrieves the name of a project's parent project.

    Returns None If |project| is not registered on Gerrit or doesn't have
    a parent (like 'All-Projects').

    Args:
      project (str): project to query.

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    code, body = self._request(
        method='GET',
        request_path='/projects/%s/parent' % urllib.quote(project, safe=''))
    if code == 404:
      return None
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)
    assert isinstance(body, unicode)
    return body if body else None

  @_not_read_only
  def set_project_parent(self, project, parent, commit_message=None):
    """Changes project's parent project.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-projects.html#set-project-parent

    Args:
      project (str): project to change.
      parent (str): parent to set.
      commit_message (str): message for corresponding refs/meta/config commit.

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    commit_message = (
        commit_message or ('Changing parent project to %s' % parent))
    code, body = self._request(
        method='PUT',
        request_path='/projects/%s/parent' % urllib.quote(project, safe=''),
        body={'parent': parent, 'commit_message': commit_message})
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)
    return body

  def query(
      self,
      project,
      query_name=None,
      with_messages=True,
      with_labels=True,
      with_revisions=True,
      **kwargs):
    """Queries the Gerrit API changes endpoint. Returns a list of ChangeInfo
    dictionaries.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#list-changes

    Args:
      project: (str) The project name.
      query_name: (str) The name of the named query stored for the CQ user.
      with_messages: (bool) If True, adds the o=MESSAGES option.
      with_labels: (bool) If True, adds the o=LABELS option.
      with_revisions: (bool) If True, adds the o=ALL_REVISIONS option.
      kwargs: Allows to specify additional query parameters.
    """

    # We always restrict queries with the project name.
    query_params = 'project:%s' % project

    if query_name:
      query_params += ' query:%s' % query_name
    for operator,value in kwargs.iteritems():
      query_params += ' %s:%s' % (operator, value)

    option_params = []
    if with_messages:
      option_params.append('MESSAGES')
    if with_labels:
      option_params.append('LABELS')
    if with_revisions:
      option_params.append('ALL_REVISIONS')

    # The requests library takes care of url encoding the params. For example
    # the spaces above in query_params will be replaced by '+'.
    params = {
        'q': query_params,
        'o': option_params
    }
    code, body = self._request(method='GET', request_path='/changes/',
                               params=params)
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  def get_issue(self, issue_id):
    """Returns a ChangeInfo dictionary for a given issue_id or None if it
    doesn't exist.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#get-change-detail

    Args:
      issue_id is gerrit issue id like project~branch~change_id.
    """
    request_path = '/changes/%s/detail' % urllib.quote(issue_id, safe='~')
    code, body = self._request(method='GET', request_path=request_path)
    if code == 404:
      return None
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  @_not_read_only
  def set_review(self, change_id, revision_id, message=None, labels=None,
                 notify=NOTIFY_NONE):
    """Uses the Set Review endpoint of the Gerrit API to add messages and/or set
    labels for a patchset.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#set-review

    Args:
      change_id: (str) The id of the change list.
      revision_id: (str) The id of the affected revision.
      message: (str) The message to add to the patchset.
      labels: (dict) The dictionary which maps label names to their new value.
      notify: (str) Who should get a notification.
    """
    if message:
      max_message = 300
      tail = u'\n(message too large)'
      if len(message) > max_message:
        message = message[:max_message-len(tail)] + tail # pragma: no cover
      logging.info('change_id: %s; comment: %s' % (change_id, message.strip()))
    payload = {}
    for var, attr in [(message, 'message'), (notify, 'notify'),
                      (labels, 'labels')]:
      if var is not None:
        payload[attr] = var
    code, body = self._request(method='POST',
                  request_path='/changes/%s/revisions/%s/review' % (
                      urllib.quote(change_id, safe='~'),
                      urllib.quote(revision_id, safe='')),
                  body=payload)
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

def _is_response_cached(method, full_url):
  """Returns True if response to GET request is in requests_cache.

  Args:
    method (str): http verb ('GET', 'POST', etc.)
    full_url (str): url, including the protocol
  Returns:
    is_cached (bool):
"""
  if method != 'GET':
    return False # pragma: no cover
  try:
    cache = requests_cache.get_cache()
  except AttributeError: # pragma: no cover
    cache = None
  return cache.has_url(full_url) if cache else False
