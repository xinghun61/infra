# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Views for Rietveld."""

# We often use local variables that are the same as handler function names, like
# "acccount", "patch", and "patchset".
# pylint: disable=W0621

import binascii
import calendar
import cgi
import datetime
import itertools
import json
import logging
import md5
import os
import random
import re
import tarfile
import tempfile
import time
import urllib
from cStringIO import StringIO
from functools import partial
from xml.etree import ElementTree

from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.datastore import datastore_query
from google.appengine.ext import db
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
from google.appengine.runtime import apiproxy_errors

from django import forms
# Import settings as django_settings to avoid name conflict with settings().
from django.conf import settings as django_settings
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotFound
from django.http import HttpResponseBadRequest
from django.shortcuts import render_to_response
import django.template
from django.template import RequestContext
from django.utils import encoding
from django.utils.html import strip_tags
from django.utils.html import urlize
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django.core.servers.basehttp import FileWrapper

import httplib2
from oauth2client.appengine import _parse_state_value
from oauth2client.appengine import _safe_html
from oauth2client.appengine import CredentialsNDBModel
from oauth2client.appengine import StorageByKeyName
from oauth2client.appengine import xsrf_secret_key
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client import xsrfutil

from codereview import auth_utils
from codereview import buildbucket
from codereview import engine
from codereview import library
from codereview import models
from codereview import models_chromium
from codereview import net
from codereview import patching
from codereview import utils
from codereview import common
from codereview.exceptions import FetchError
from codereview.responses import HttpTextResponse, HttpHtmlResponse, respond
import codereview.decorators as deco
import gae_ts_mon


# Add our own custom template tags library.
django.template.add_to_builtins('codereview.library')


### Constants ###

REQUIRED_REVIEWERS_HELP_TEXT = (
    'Use asterisks to specify required reviewers. Eg: *xyz, abc')

OAUTH_DEFAULT_ERROR_MESSAGE = 'OAuth 2.0 error occurred.'
_ACCESS_TOKEN_TEMPLATE_ROOT = 'http://localhost:%(port)d?'
ACCESS_TOKEN_REDIRECT_TEMPLATE = (_ACCESS_TOKEN_TEMPLATE_ROOT +
                                  'access_token=%(token)s')
ACCESS_TOKEN_FAIL_REDIRECT_TEMPLATE = (_ACCESS_TOKEN_TEMPLATE_ROOT +
                                       'error=%(error)s')
# Maximum forms fields length
MAX_SUBJECT = 100
MAX_DESCRIPTION = 10000
MAX_URL = 2083
MAX_REVIEWERS = 1000
MAX_CC = 50000
MAX_MESSAGE = 10000
MAX_FILENAME = 255
MAX_DB_KEY_LENGTH = 1000

DB_WRITE_TRIES = 3
DB_WRITE_PAUSE = 4

CQ_SERVICE_ACCOUNT = ('5071639625-1lppvbtck1morgivc6sq4dul7klu27sd@'
                      'developer.gserviceaccount.com')
CQ_COMMIT_BOT_EMAIL = 'commit-bot@chromium.org'


### Form classes ###


class AccountInput(forms.TextInput):
  # Associates the necessary css/js files for the control.  See
  # http://docs.djangoproject.com/en/dev/topics/forms/media/.
  #
  # Don't forget to place {{formname.media}} into html header
  # when using this html control.
  class Media:
    css = {
      'all': ('autocomplete/jquery.autocomplete.css',)
    }
    js = (
      'autocomplete/lib/jquery.js',
      'autocomplete/lib/jquery.bgiframe.min.js',
      'autocomplete/lib/jquery.ajaxQueue.js',
      'autocomplete/jquery.autocomplete.js'
    )

  def render(self, name, value, attrs=None):
    output = super(AccountInput, self).render(name, value, attrs)
    if models.Account.current_user_account is not None:
      # TODO(anatoli): move this into .js media for this form
      data = {'name': name, 'url': reverse(account),
              'multiple': 'true'}
      if self.attrs.get('multiple', True) == False:
        data['multiple'] = 'false'
      output += mark_safe(u'''
      <script type="text/javascript">
          jQuery("#id_%(name)s").autocomplete("%(url)s", {
          max: 10,
          highlight: false,
          multiple: %(multiple)s,
          multipleSeparator: ", ",
          scroll: true,
          scrollHeight: 300,
          matchContains: true,
          formatResult : function(row) {
          return row[0].replace(/ .+/gi, '');
          }
          });
      </script>''' % data)
    return output


class BlockForm(forms.Form):
  blocked = forms.BooleanField(
      required=False,
      help_text='Should this user be blocked')


FORM_CONTEXT_VALUES = [(z, '%d lines' % z) for z in models.CONTEXT_CHOICES]
FORM_CONTEXT_VALUES.append(('', 'Whole file'))


class SettingsForm(forms.Form):

  nickname = forms.CharField(max_length=30)
  context = forms.IntegerField(
      widget=forms.Select(choices=FORM_CONTEXT_VALUES),
      required=False,
      label='Context')
  column_width = forms.IntegerField(
      initial=django_settings.DEFAULT_COLUMN_WIDTH,
      min_value=django_settings.MIN_COLUMN_WIDTH,
      max_value=django_settings.MAX_COLUMN_WIDTH)
  tab_spaces = forms.IntegerField(
      initial=django_settings.DEFAULT_TAB_SPACES,
      min_value=django_settings.MIN_TAB_SPACES,
      max_value=django_settings.MAX_TAB_SPACES)
  deprecated_ui = forms.BooleanField(required=False)
  notify_by_email = forms.BooleanField(required=False,
                                       widget=forms.HiddenInput())
  notify_by_chat = forms.BooleanField(
      required=False,
      help_text='You must accept the invite for this to work.')

  add_plus_role = forms.BooleanField(
      required=False,
      help_text=('Add +owner, +reviewer, or +cc to my email address '
                 'when sending notifications.'))

  display_generated_msgs = forms.BooleanField(
      required=False,
      help_text='Display generated messages by default.')

  display_exp_tryjob_results = forms.BooleanField(
      widget=forms.Select(choices=[
          (False, 'Never'),
          (True, 'On issues that have experimental results')]),
      required=False,
      label='Display experimental tryjob results')

  send_from_email_addr = forms.BooleanField(
      required=False,
      help_text='Send notification emails from my email address.')


  def clean_nickname(self):
    nickname = self.cleaned_data.get('nickname')
    # Check for allowed characters
    match = re.match(r'[\w\.\-_\(\) ]+$', nickname, re.UNICODE|re.IGNORECASE)
    if not match:
      raise forms.ValidationError('Allowed characters are letters, digits, '
                                  '".-_()" and spaces.')
    # Check for sane whitespaces
    if re.search(r'\s{2,}', nickname):
      raise forms.ValidationError('Use single spaces between words.')
    if len(nickname) != len(nickname.strip()):
      raise forms.ValidationError('Leading and trailing whitespaces are '
                                  'not allowed.')

    if nickname.lower() == 'me':
      raise forms.ValidationError('Choose a different nickname.')

    # Look for existing nicknames
    # This uses eventual consistency and cannot be made strongly consistent.
    query = models.Account.query(
        models.Account.lower_nickname == nickname.lower())
    if any(
        account.key != models.Account.current_user_account.key
        for account in query):
      raise forms.ValidationError('This nickname is already in use.')

    return nickname


ORDER_CHOICES = (
    '__key__',
    'owner',
    'created',
    'modified',
)

class SearchForm(forms.Form):

  format = forms.ChoiceField(
      required=False,
      choices=(
        ('html', 'html'),
        ('json', 'json')),
      widget=forms.HiddenInput(attrs={'value': 'html'}))
  keys_only = forms.BooleanField(
      required=False,
      widget=forms.HiddenInput(attrs={'value': 'False'}))
  with_messages = forms.BooleanField(
      required=False,
      widget=forms.HiddenInput(attrs={'value': 'False'}))
  cursor = forms.CharField(
      required=False,
      widget=forms.HiddenInput(attrs={'value': ''}))
  limit = forms.IntegerField(
      required=False,
      min_value=1,
      max_value=1000,
      widget=forms.HiddenInput(attrs={'value': '30'}))
  closed = forms.NullBooleanField(required=False)
  owner = forms.CharField(required=False,
                          max_length=MAX_REVIEWERS,
                          widget=AccountInput(attrs={'size': 60,
                                                     'multiple': False}))
  reviewer = forms.CharField(required=False,
                             max_length=MAX_REVIEWERS,
                             widget=AccountInput(attrs={'size': 60,
                                                        'multiple': False}))
  cc = forms.CharField(required=False,
                       max_length=MAX_CC,
                       label = 'CC',
                       widget=AccountInput(attrs={'size': 60}))
  repo_guid = forms.CharField(required=False, max_length=MAX_URL,
                              label="Repository ID")
  base = forms.CharField(required=False, max_length=MAX_URL)
  project = forms.CharField(required=False, max_length=MAX_URL)
  private = forms.NullBooleanField(required=False)
  commit = forms.NullBooleanField(required=False)
  created_before = forms.DateTimeField(
    required=False, label='Created before',
    help_text='Format: YYYY-MM-DD and optional: hh:mm:ss')
  created_after = forms.DateTimeField(
      required=False, label='Created on or after')
  modified_before = forms.DateTimeField(required=False, label='Modified before')
  modified_after = forms.DateTimeField(
      required=False, label='Modified on or after')
  order = forms.ChoiceField(
      required=False, help_text='Order: Name of one of the datastore keys',
      choices=sum(
        ([(x, x), ('-' + x, '-' + x)] for x in ORDER_CHOICES),
        [('', '(default)')]))

  def _clean_accounts(self, key):
    """Cleans up autocomplete field.

    The input is validated to be zero or one name/email and it's
    validated that the users exists.

    Args:
      key: the field name.

    Returns an User instance or raises ValidationError.
    """
    user_names = filter(None,
                        (x.strip()
                         for x in self.cleaned_data.get(key, '').split(',')))
    if len(user_names) > 1:
      raise forms.ValidationError('Only one user name is allowed.')
    elif not user_names:
      return None
    user_name = user_names[0]
    if '@' in user_name:
      acct = models.Account.get_account_for_email(user_name)
    else:
      acct = models.Account.get_account_for_nickname(user_name)
    if not acct:
      raise forms.ValidationError('Unknown user')
    return acct.user

  def clean_owner(self):
    return self._clean_accounts('owner')

  def clean_reviewer(self):
    user = self._clean_accounts('reviewer')
    if user:
      return user.email()


class StringListField(forms.CharField):

  def prepare_value(self, value):
    if value is None:
      return ''
    return ','.join(value)

  def to_python(self, value):
    if not value:
      return []
    return [list_value.strip() for list_value in value.split(',')]


class ClientIDAndSecretForm(forms.Form):
  """Simple form for collecting Client ID and Secret."""
  client_id = forms.CharField(
    help_text='Enter a single service account Client ID.',
    widget=forms.TextInput(attrs={'size': '100'}))
  client_secret = forms.CharField(
    required=False,
    widget=forms.TextInput(attrs={'size': '100'}))
  additional_client_ids = StringListField(
    required=False,
    help_text='Enter a comma-separated list of Client IDs.',
    widget=forms.TextInput(attrs={'size': '100'}))
  whitelisted_emails = StringListField(
    required=False,
    help_text='Enter a comma-separated list of email addresses to whitelist.',
    widget=forms.TextInput(attrs={'size': '100'}))


### Exceptions ###


class InvalidIncomingEmailError(Exception):
  """Exception raised by incoming mail handler when a problem occurs."""


### Helper functions ###


def _clean_int(value, default, min_value=None, max_value=None):
  """Helper to cast value to int and to clip it to min or max_value.

  Args:
    value: Any value (preferably something that can be casted to int).
    default: Default value to be used when type casting fails.
    min_value: Minimum allowed value (default: None).
    max_value: Maximum allowed value (default: None).

  Returns:
    An integer between min_value and max_value.
  """
  if not isinstance(value, (int, long)):
    try:
      value = int(value)
    except (TypeError, ValueError):
      value = default
  if min_value is not None:
    value = max(min_value, value)
  if max_value is not None:
    value = min(value, max_value)
  return value


def _use_new_ui(request):
  if (not models.Account.current_user_account or
      models.Account.current_user_account.deprecated_ui):
    return False
  if request.path.find('scrape') != -1:
    return False
  return True


def _serve_new_ui(request):
  return respond(request, "new_ui.html", {})


### Request handlers ###


def index(request):
  """/ - Show a list of review issues"""
  if _use_new_ui(request):
    return _serve_new_ui(request)

  if request.user is None:
    return view_all(request, index_call=True)
  else:
    return mine(request)


DEFAULT_LIMIT = 20


def _url(path, **kwargs):
  """Format parameters for query string.

  Args:
    path: Path of URL.
    kwargs: Keyword parameters are treated as values to add to the query
      parameter of the URL.  If empty no query parameters will be added to
      path and '?' omitted from the URL.
  """
  if kwargs:
    if isinstance(kwargs.get('owner'), users.User):
      kwargs['owner'] = kwargs['owner'].email()
    encoded_parameters = urllib.urlencode(kwargs)
    if path.endswith('?'):
      # Trailing ? on path.  Append parameters to end.
      return '%s%s' % (path, encoded_parameters)
    elif '?' in path:
      # Append additional parameters to existing query parameters.
      return '%s&%s' % (path, encoded_parameters)
    else:
      # Add query parameters to path with no query parameters.
      return '%s?%s' % (path, encoded_parameters)
  else:
    return path


def _inner_paginate(request, issues, template, extra_template_params):
  """Display paginated list of issues.

  Takes care of the private bit.

  Args:
    request: Request containing offset and limit parameters.
    issues: Issues to be displayed.
    template: Name of template that renders issue page.
    extra_template_params: Dictionary of extra parameters to pass to page
      rendering.

  Returns:
    Response for sending back to browser.
  """
  visible_issues = [i for i in issues if i.view_allowed]
  _optimize_draft_counts(visible_issues)
  _load_users_for_issues(visible_issues)
  params = {
    'issues': visible_issues,
    'limit': None,
    'newest': None,
    'prev': None,
    'next': None,
    'nexttext': '',
    'first': '',
    'last': '',
  }
  if extra_template_params:
    params.update(extra_template_params)
  return respond(request, template, params)


def _paginate_issues(page_url,
                     request,
                     query,
                     template,
                     extra_nav_parameters=None,
                     extra_template_params=None):
  """Display paginated list of issues.

  Args:
    page_url: Base URL of issue page that is being paginated.  Typically
      generated by calling 'reverse' with a name and arguments of a view
      function.
    request: Request containing offset and limit parameters.
    query: Query over issues.
    template: Name of template that renders issue page.
    extra_nav_parameters: Dictionary of extra parameters to append to the
      navigation links.
    extra_template_params: Dictionary of extra parameters to pass to page
      rendering.

  Returns:
    Response for sending back to browser.
  """
  offset = _clean_int(request.GET.get('offset'), 0, 0)
  limit = _clean_int(request.GET.get('limit'), DEFAULT_LIMIT, 1, 100)

  nav_parameters = {'limit': str(limit)}
  if extra_nav_parameters is not None:
    nav_parameters.update(extra_nav_parameters)

  params = {
    'limit': limit,
    'first': offset + 1,
    'nexttext': 'Older',
  }
  # Fetch one more to see if there should be a 'next' link
  logging.info('query during pagination is %r', query)
  issues = query.fetch(limit+1, offset=offset)
  if len(issues) > limit:
    del issues[limit:]
    params['next'] = _url(page_url, offset=offset + limit, **nav_parameters)
  params['last'] = len(issues) > 1 and offset+len(issues) or None
  if offset > 0:
    params['prev'] = _url(page_url, offset=max(0, offset - limit),
        **nav_parameters)
  if offset > limit:
    params['newest'] = _url(page_url, **nav_parameters)
  if extra_template_params:
    params.update(extra_template_params)
  return _inner_paginate(request, issues, template, params)


def _paginate_issues_with_cursor(page_url,
                                 request,
                                 query,
                                 cursor,
                                 limit,
                                 template,
                                 extra_nav_parameters=None,
                                 extra_template_params=None):
  """Display paginated list of issues using a cursor instead of offset.

  Args:
    page_url: Base URL of issue page that is being paginated.  Typically
      generated by calling 'reverse' with a name and arguments of a view
      function.
    request: Request containing offset and limit parameters.
    query: Query over issues
    cursor: cursor object passed to web form and back again.
    limit: Maximum number of issues to return.
    template: Name of template that renders issue page.
    extra_nav_parameters: Dictionary of extra parameters to append to the
      navigation links.
    extra_template_params: Dictionary of extra parameters to pass to page
      rendering.

  Returns:
    Response for sending back to browser.
  """
  issues, next_cursor, has_more = query.fetch_page(limit, start_cursor=cursor)
  nav_parameters = {}
  if extra_nav_parameters:
    nav_parameters.update(extra_nav_parameters)
  nav_parameters['cursor'] = next_cursor.urlsafe() if next_cursor else ''

  params = {
    'limit': limit,
    'cursor': nav_parameters['cursor'],
    'nexttext': 'Next',
  }
  if has_more:
    params['next'] = _url(page_url, **nav_parameters)
  if extra_template_params:
    params.update(extra_template_params)
  return _inner_paginate(request, issues, template, params)


def view_all(request, index_call=False):
  """/all - Show a list of up to DEFAULT_LIMIT recent issues."""
  closed = request.GET.get('closed', '')
  if closed in ('0', 'false'):
    closed = False
  elif closed in ('1', 'true'):
    closed = True
  elif index_call:
    # for index we display only open issues by default
    closed = False
  else:
    closed = None

  nav_parameters = {}
  if closed is not None:
    nav_parameters['closed'] = int(closed)

  # This uses eventual consistency and cannot be made strongly consistent.
  query = models.Issue.query(
      models.Issue.private == False).order(-models.Issue.modified)
  if closed is not None:
    # return only opened or closed issues
    query = query.filter(models.Issue.closed == closed)

  return _paginate_issues(reverse(view_all),
                          request,
                          query,
                          'all.html',
                          extra_nav_parameters=nav_parameters,
                          extra_template_params=dict(closed=closed))


def _optimize_draft_counts(issues):
  """Force _num_drafts to zero for issues that are known to have no drafts.

  Args:
    issues: list of model.Issue instances.

  This inspects the drafts attribute of the current user's Account
  instance, and forces the draft count to zero of those issues in the
  list that aren't mentioned there.

  If there is no current user, all draft counts are forced to 0.
  """
  cur_account = models.Account.current_user_account
  if cur_account is None:
    issue_ids = None
  else:
    issue_ids = cur_account.drafts
  for issue in issues:
    if issue_ids is None or issue.key.id() not in issue_ids:
      issue._num_drafts = issue._num_drafts or {}
      if cur_account:
        issue._num_drafts[cur_account.email] = 0


@deco.login_required
@deco.require_methods('GET')
def mine(request):
  """/mine - Show a list of issues created by the current user."""
  request.user_to_show = request.user
  return _show_user(request)


@deco.json_response
@deco.user_key_required
@deco.require_methods('GET')
def api_user_inbox(request):
  """/api/user_inbox/USER - JSON dict of lists of issues for the polymer
  dashboard.
  """
  def issue_to_inbox_json(issue):
    """Get the JSON for an issue, then add draft and comment counts."""

    values = {
      'owner_email': issue.owner.email(),
      'modified': str(issue.modified),
      'reviewer_scores': _scored_reviewers(issue),
      'subject': issue.subject,
      'issue': issue.key.id(),
      'has_updates': issue.has_updates,
    }
    return values

  dashboard_dict = _get_dashboard_issue_lists(
      request, load_users_and_drafts=False)
  result = {
    key: [issue_to_inbox_json(issue) for issue in issue_list]
    for key, issue_list in dashboard_dict.iteritems()}
  return result


def _scored_reviewers(issue):
  result = {}
  for email, value in issue.formatted_reviewers.iteritems():
    if value == True:
      result[email] = 1
    elif value == False:
      result[email] = -1
  return result


@deco.login_required
@deco.require_methods('GET')
def starred(request):
  """/starred - Show a list of issues starred by the current user."""
  stars = models.Account.current_user_account.stars
  if not stars:
    issues = []
  else:
    starred_issue_keys = [ndb.Key(models.Issue, i) for i in stars]
    issues = [issue for issue in ndb.get_multi(starred_issue_keys)
              if issue and issue.view_allowed]
    _load_users_for_issues(issues)
    _optimize_draft_counts(issues)
  return respond(request, 'starred.html', {'issues': issues})


def _load_users_for_issues(issues):
  """Load all user links for a list of issues in one go."""
  user_dict = {}
  for i in issues:
    for e in i.reviewers + i.cc + [i.owner.email()]:
      # keeping a count lets you track total vs. distinct if you want
      user_dict[e] = user_dict.setdefault(e, 0) + 1

  library.get_links_for_users(user_dict.keys())


@deco.user_key_required
@deco.require_methods('GET')
def show_user(request):
  """/user - Show the user's dashboard"""
  return _show_user(request)


def _get_dashboard_issue_lists(request, load_users_and_drafts=True):
  """Return a dict {string: [issue]} of the issues to show on a dashboard."""
  user = request.user_to_show
  if user == request.user:
  # This uses eventual consistency and cannot be made strongly consistent.
    draft_query = models.Comment.query(
        models.Comment.draft == True, models.Comment.author == request.user)
    draft_issue_keys = {
        draft_key.parent().parent().parent()
        for draft_key in draft_query.fetch(100, keys_only=True)}
    draft_issues = ndb.get_multi(draft_issue_keys)
  else:
    draft_issues = draft_issue_keys = []

  earliest_closed = datetime.datetime.utcnow() - datetime.timedelta(days=7)

  # These use eventual consistency and cannot be made strongly consistent.
  my_issues_query = models.Issue.query(
      models.Issue.closed == False, models.Issue.owner == user).order(
        -models.Issue.modified).fetch_async(100)
  review_issues_query = models.Issue.query(
      models.Issue.closed == False,
      models.Issue.reviewers == user.email().lower()).order(
        -models.Issue.modified).fetch_async(100)
  closed_issues_query = models.Issue.query(
          models.Issue.closed == True,
          models.Issue.modified > earliest_closed,
          models.Issue.owner == user).order(
            -models.Issue.modified).fetch_async(100)
  cc_issues_query = models.Issue.query(
          models.Issue.closed == False, models.Issue.cc == user.email()).order(
            -models.Issue.modified).fetch_async(100)

  my_issues = [
      issue for issue in my_issues_query.get_result()
      if issue.key not in draft_issue_keys and issue.view_allowed]
  review_issues = [
      issue for issue in review_issues_query.get_result()
      if (issue.key not in draft_issue_keys and issue.owner != user
          and issue.view_allowed)]
  closed_issues = [
      issue for issue in closed_issues_query.get_result()
      if issue.key not in draft_issue_keys and issue.view_allowed]
  cc_issues = [
      issue for issue in cc_issues_query.get_result()
      if (issue.key not in draft_issue_keys and issue.owner != user
          and issue.view_allowed)]
  all_issues = my_issues + review_issues + closed_issues + cc_issues

  # Some of these issues may not have accurate updates_for information,
  # so ask each issue to update itself.
  futures = []
  for issue in itertools.chain(draft_issues, all_issues):
    ret = issue.calculate_and_save_updates_if_None()
    if ret is not None:
      futures.append(ret)
  ndb.Future.wait_all(futures)

  # When a CL is sent from upload.py using --send_mail we create an empty
  # message. This might change in the future, either by not adding an empty
  # message or by populating the message with the content of the email
  # that was sent out.
  outgoing_issues = [issue for issue in my_issues if issue.num_messages]
  unsent_issues = [issue for issue in my_issues if not issue.num_messages]

  if load_users_and_drafts:
    _load_users_for_issues(all_issues)
    _optimize_draft_counts(all_issues)

  return {
    'outgoing_issues': outgoing_issues,
    'unsent_issues': unsent_issues,
    'review_issues': review_issues,
    'closed_issues': closed_issues,
    'cc_issues': cc_issues,
    'draft_issues': draft_issues,
    }


def _show_user(request):
  if _use_new_ui(request):
    return _serve_new_ui(request)

  dashboard_dict = _get_dashboard_issue_lists(request)
  viewed_account = models.Account.get_account_for_user(
    request.user_to_show, autocreate=False)
  if not viewed_account:
    return HttpTextResponse(
      'No such user (%s)' % request.user_to_show.email(), status=404)

  show_block = request.user_is_admin and request.user_to_show != request.user
  dashboard_dict.update({
      'viewed_account': viewed_account,
      'show_block': show_block,
      })
  return respond(request, 'user.html', dashboard_dict)


@deco.access_control_allow_origin_star
# TODO(agable): remove POST after crrev.com/c/723824 lands.
@deco.require_methods('GET', 'POST')
@deco.patchset_required
@deco.json_response
def get_depends_on_patchset(request):
  """/<issue>/get_depends_on_patchset- The patchset this patchset depends on."""
  response = {}
  if request.patchset.depends_on_patchset:
    # Verify that the depended upon issue is not closed.
    tokens = request.patchset.depends_on_patchset.split(':')
    depends_on_issue = models.Issue.get_by_id(int(tokens[0]))
    if depends_on_issue and not depends_on_issue.closed:
      response = {
          'issue': tokens[0],
          'patchset': tokens[1],
      }
  return response


@deco.admin_required
@deco.user_key_required
@deco.xsrf_required
@deco.require_methods('GET', 'POST')
def block_user(request):
  """/user/<user>/block - Blocks a specific user."""
  account = models.Account.get_account_for_user(request.user_to_show)
  if request.method == 'POST':
    form = BlockForm(request.POST)
    if form.is_valid():
      account.blocked = form.cleaned_data['blocked']
      logging.debug(
          'Updating block bit to %s for user %s',
          account.blocked,
          account.email)
      account.put()
      if account.blocked:
        # Remove user from existing issues so that he doesn't participate in
        # email communication anymore.
        # These use eventual consistency and cannot be made strongly consistent.
        tbd = {}
        email = account.user.email()
        query = models.Issue.query(models.Issue.reviewers == email)
        for issue in query:
          issue.reviewers.remove(email)
          issue.calculate_updates_for()
          tbd[issue.key] = issue
        # look for issues where blocked user is in cc only
        query = models.Issue.query(models.Issue.cc == email)
        for issue in query:
          if issue.key in tbd:
            # Update already changed instance instead. This happens when the
            # blocked user is in both reviewers and ccs.
            issue = tbd[issue.key]
          issue.cc.remove(account.user.email())
          tbd[issue.key] = issue
        ndb.put_multi(tbd.values())
  else:
    form = BlockForm()
  form.initial['blocked'] = account.blocked
  templates = {
    'viewed_account': account,
    'form': form,
  }
  return respond(request, 'block_user.html', templates)


def _replace_bug(message):
  dit_base_tracker_url = 'http://code.google.com/p/%s/issues/detail?id=%s'
  dit_valid_trackers = ('chrome-os-partner', 'chromium-os', 'libyuv')
  monorail_base_tracker_url = (
      'https://bugs.chromium.org/p/%s/issues/detail?id=%s')
  monorail_valid_trackers = ('chromium', 'crashpad', 'gyp', 'monorail',
                             'pdfium', 'skia', 'v8', 'webrtc')

  bugs = re.split(r"[\s,]+", message.group(1))
  urls = []
  for bug in bugs:
    if not bug:
      continue
    tracker = 'chromium'
    if ':' in bug:
      tracker, bug_id = bug.split(':', 1)
      if tracker not in dit_valid_trackers + monorail_valid_trackers:
        urls.append(bug)
        continue
    else:
      bug_id = bug
    # If a project is not specified then use Monorail by default.
    if tracker in dit_valid_trackers:
      base_tracker_url = dit_base_tracker_url
    else:
      base_tracker_url = monorail_base_tracker_url
    url = '<a href="' + base_tracker_url % (tracker, bug_id) + '">'
    urls.append(url + bug + '</a>')

  return ", ".join(urls) + "\n"


def _map_base_url(base):
  """Check if Base URL can be converted into a source code viewer URL."""
  # This uses eventual consistency and cannot be made strongly consistent.
  for rule in models_chromium.UrlMap.query().order(
      models_chromium.UrlMap.base_url_template):
    base_template = r'^%s$' % rule.base_url_template
    match = re.match(base_template, base)
    if not match:
      continue
    try:
      src_url = re.sub(base_template,
                       rule.source_code_url_template,
                       base)
    except re.error, err:
      logging.error('err: %s base: "%s" rule: "%s" => "%s"',
                    err, base, rule.base_url_template,
                    rule.source_code_url_template)
      return None
    return src_url
  return None


@deco.issue_required
@deco.require_methods('GET')
def show(request):
  """/<issue> - Show an issue."""
  if _use_new_ui(request):
    return _serve_new_ui(request)

  patchsets = request.issue.get_patchset_info(request.user, None)
  last_patchset = first_patch = None
  if patchsets:
    last_patchset = patchsets[-1]
    if last_patchset.patches:
      first_patch = last_patchset.patches[0]
  messages = []
  generated_messages = []
  has_draft_message = False
  # Keep track of the last non-generated message.
  message_index = -1
  last_user_message_index = -1
  for msg in request.issue.messages:
    if msg.auto_generated:
      generated_messages.append(msg)
    if not msg.draft:
      messages.append(msg)
      message_index += 1
      if not msg.auto_generated:
        last_user_message_index = message_index
    elif msg.draft and request.user and msg.sender == request.user.email():
      has_draft_message = True
  num_patchsets = len(patchsets)

  issue = request.issue
  issue.description = cgi.escape(issue.description)
  issue.description = urlize(issue.description)
  re_string = r"(?<=BUG=)"
  re_string += "(\s*(?:[a-z0-9-]+:)?\d+\s*(?:,\s*(?:[a-z0-9-]+:)?\d+\s*)*)"
  expression = re.compile(re_string, re.IGNORECASE)
  issue.description = re.sub(expression, _replace_bug, issue.description)
  src_url = _map_base_url(issue.base)

  display_generated_msgs = False
  display_exp_tryjob_results = False
  if request.user:
    account = models.Account.current_user_account
    display_generated_msgs = account.display_generated_msgs
    display_exp_tryjob_results = account.display_exp_tryjob_results

  # Generate the set of possible parents for every builder name, if a
  # builder could have 2 different parents, then append the parent name to
  # the builder to differentiate them.
  builds_to_parents = {}
  has_exp_jobs = False
  try_job_loading_error = False
  try_job_results = []
  try:
    try_job_results = _get_patchset_try_job_results(last_patchset)
    for try_job in try_job_results:
      if try_job.parent_name:
        builds_to_parents.setdefault(try_job.builder,
                                     set()).add(try_job.parent_name)
      if try_job.category == 'cq_experimental':
        has_exp_jobs = True

    if display_exp_tryjob_results and not has_exp_jobs:
      display_exp_tryjob_results = False

    for try_job in try_job_results:
      if try_job.parent_name and len(builds_to_parents[try_job.builder]) > 1:
        try_job.builder = try_job.parent_name + ':' + try_job.builder
  except Exception:
    # Do not crash, but degrade.
    logging.exception('Error while loading try job results')
    try_job_loading_error = True

  return respond(request, 'issue.html', {
    'default_builders':
      models_chromium.TryserverBuilders.get_builders(),
    'first_patch': first_patch,
    'has_draft_message': has_draft_message,
    'is_editor': request.issue.edit_allowed,
    'issue': request.issue,
    'last_patchset': last_patchset,
    'messages': messages,
    'generated_messages': generated_messages,
    'last_user_message_index': last_user_message_index,
    'num_patchsets': num_patchsets,
    'patchsets': patchsets,
    'try_job_results': try_job_results,
    'try_job_loading_error': try_job_loading_error,
    'src_url': src_url,
    'display_generated_msgs': display_generated_msgs,
    'display_exp_tryjob_results': display_exp_tryjob_results,
    'offer_cq': request.issue.is_cq_available,
    'landed_days_ago': issue.get_time_since_landed() or 'unknown',
  })


def _get_patchset_try_job_results(patchset, swallow_exceptions=True):
  """Returns a list of try job results for the |patchset|.

  Combines try job results stored in datastore and in buildbucket. Deduplicates
  builds that have same buildbucket build id.
  """
  issue = patchset.issue_key.get()
  # Fetch try job results from NDB and Buildbucket in parallel.
  buildbucket_results_future = (
      buildbucket.get_try_job_results_for_patchset_async(
          issue.project, patchset.issue_key.id(), patchset.key.id()))
  local_try_job_results = patchset.try_job_results

  try_job_results = []
  buildbucket_build_ids = set()
  try:
    for result in buildbucket_results_future.get_result():
      try_job_results.append(result)
      buildbucket_build_ids.add(result.build_id)
  except net.AuthError:
    logging.exception('Could not load buildbucket builds')
    if not swallow_exceptions:
      raise

  def try_get_build_id(try_job_result):
    if not try_job_result.build_properties:
      return None
    try:
      props = json.loads(try_job_result.build_properties)
    except ValueError:
      return None
    if not isinstance(props, dict):
      return None

    def get_subdict(d, key):
      v = d.get(key, {})
      if isinstance(v, basestring):
        v = json.loads(v)
      if not isinstance(v, dict):
        logging.error(
            'Could not parse buildbucket build property. Properties: %r', props)
        return {}
      return v

    bb_info = get_subdict(props, 'buildbucket')
    return (
        get_subdict(bb_info, 'build').get('id') or
        bb_info.get('build_id'))

  for result in local_try_job_results:
    build_id = try_get_build_id(result)
    if build_id is None or build_id not in buildbucket_build_ids:
      try_job_results.append(result)

  return try_job_results


@deco.patchset_required
@deco.require_methods('GET')
def patchset(request):
  """/patchset/<key> - Returns patchset information."""
  display_exp_tryjob_results = False
  if request.user:
    account = models.Account.current_user_account
    display_exp_tryjob_results = account.display_exp_tryjob_results
  patchsets = request.issue.get_patchset_info(
    request.user, request.patchset.key.id())
  for ps in patchsets:
    if ps.key.id() == request.patchset.key.id():
      patchset = ps

  try_job_results = _get_patchset_try_job_results(patchset)
  if display_exp_tryjob_results:
    has_exp_jobs = False
    for try_job in try_job_results:
      if try_job.category == 'cq_experimental':
        has_exp_jobs = True
        break
    if not has_exp_jobs:
      logging.debug('no experiments')
      display_exp_tryjob_results = False
  logging.debug('tryjobs: %s' % try_job_results)

  return respond(request, 'patchset.html',
                 {'issue': request.issue,
                  'patchset': request.patchset,
                  'try_job_results': try_job_results,
                  'patchsets': patchsets,
                  'is_editor': request.issue.edit_allowed,
                  'display_exp_tryjob_results': display_exp_tryjob_results,
                  })


@deco.login_required
@deco.require_methods('GET')
def account(request):
  """/account/?q=blah&limit=10&timestamp=blah - Used for autocomplete."""
  def searchAccounts(prop, domain, added, response):
    prefix = request.GET.get('q').lower()
    required_reviewer = prefix.startswith(models.REQUIRED_REVIEWER_PREFIX)
    prefix = prefix.lstrip(models.REQUIRED_REVIEWER_PREFIX)
    limit = _clean_int(request.GET.get('limit'), 10, 10, 100)

    # This uses eventual consistency and cannot be made strongly consistent.
    accounts_query = models.Account.query(
        prop >= prefix, prop < prefix + u"\ufffd").order(prop)
    for account in accounts_query:
      if account.blocked:
        continue
      if account.key in added:
        continue
      if domain and not account.email.endswith(domain):
        continue
      if len(added) >= limit:
        break
      added.add(account.key)
      if required_reviewer:
        response += models.REQUIRED_REVIEWER_PREFIX
      response += '%s (%s)\n' % (account.email, account.nickname)
    return added, response

  added = set()
  response = ''
  domain = os.environ['AUTH_DOMAIN']
  if domain != 'gmail.com':
    # 'gmail.com' is the value AUTH_DOMAIN is set to if the app is running
    # on appspot.com and shouldn't prioritize the custom domain.
    added, response = searchAccounts(
      models.Account.lower_email, domain, added, response)
    added, response = searchAccounts(
      models.Account.lower_nickname, domain, added, response)

  added, response = searchAccounts(
    models.Account.lower_nickname, "", added, response)
  added, response = searchAccounts(
    models.Account.lower_email, "", added, response)
  return HttpTextResponse(response)


@deco.access_control_allow_origin_star
@deco.patchset_required
@deco.require_methods('GET')
def download(request):
  """/download/<issue>_<patchset>.diff - Download a patch set."""
  if request.patchset.data is None:
    return HttpTextResponse(
        'Patch set (%s) is too large.' % request.patchset.key.id(),
        status=404)
  padding = ''
  user_agent = request.META.get('HTTP_USER_AGENT')
  if user_agent and 'MSIE' in user_agent:
    # Add 256+ bytes of padding to prevent XSS attacks on Internet Explorer.
    padding = ('='*67 + '\n') * 4
  return HttpTextResponse(padding + request.patchset.data)


@deco.patchset_required
@deco.require_methods('GET')
def tarball(request):
  """/tarball/<issue>/<patchset>/[lr] - Returns a .tar.bz2 file
  containing a/ and b/ trees of the complete files for the entire patchset."""

  patches = (models.Patch
             .query(ancestor=request.patchset.key)
             .order(models.Patch.filename)
             .fetch(1000))

  temp = tempfile.TemporaryFile()
  tar = tarfile.open(mode="w|bz2", fileobj=temp)

  def add_entry(prefix, content, patch):
    data = content.data
    if data is None:
      data = content.text
      if isinstance(data, unicode):
        data = data.encode("utf-8", "replace")
    if data is None:
      return
    info = tarfile.TarInfo(prefix + patch.filename)
    info.size = len(data)
    # TODO(adonovan): set SYMTYPE/0755 when Rietveld supports symlinks.
    info.type = tarfile.REGTYPE
    info.mode = 0644
    # datetime->time_t
    delta = request.patchset.modified - datetime.datetime(1970, 1, 1)
    info.mtime = int(delta.days * 86400 + delta.seconds)
    tar.addfile(info, fileobj=StringIO(data))

  for patch in patches:
    if not patch.no_base_file:
      try:
        add_entry('a/', patch.get_content(), patch)  # before
      except FetchError:  # I/O problem?
        logging.exception('tarball: patch(%s, %s).get_content failed' %
                          (patch.key.id(), patch.filename))
    try:
      add_entry('b/', patch.get_patched_content(), patch)  # after
    except FetchError:  # file deletion?  I/O problem?
      logging.exception('tarball: patch(%s, %s).get_patched_content failed' %
                        (patch.key.id(), patch.filename))

  tar.close()
  temp.flush()

  wrapper = FileWrapper(temp)
  response = HttpResponse(wrapper, mimetype='application/x-gtar')
  response['Content-Disposition'] = (
      'attachment; filename=patch%s_%s.tar.bz2' % (request.issue.key.id(),
                                                   request.patchset.key.id()))
  response['Content-Length'] = temp.tell()
  temp.seek(0)
  return response


@deco.issue_required
@deco.require_methods('GET')
def description(request):
  """/<issue>/description - Gets an issue's description."""
  description = request.issue.description or ""
  return HttpTextResponse(description)


@deco.issue_required
@deco.json_response
@deco.require_methods('GET')
def fields(request):
  """/<issue>/fields - Gets fields on the issue."""
  fields = request.GET.getlist('field')
  response = {}
  if 'reviewers' in fields:
    response['reviewers'] = request.issue.reviewers or []
  if 'description' in fields:
    response['description'] = request.issue.description
  if 'subject' in fields:
    response['subject'] = request.issue.subject
  return response


@deco.patch_required
@deco.require_methods('GET')
def patch(request):
  """/<issue>/patch/<patchset>/<patch> - View a raw patch."""
  if _use_new_ui(request):
    return _serve_new_ui(request)
  return _patch_helper(request)


def _patch_helper(request, nav_type='patch'):
  """Returns a unified diff.

  Args:
    request: Django Request object.
    nav_type: the navigation used in the url (i.e. patch/diff/diff2).  Normally
      the user looks at either unified or side-by-side diffs at one time, going
      through all the files in the same mode.  However, if side-by-side is not
      available for some files, we temporarly switch them to unified view, then
      switch them back when we can.  This way they don't miss any files.

  Returns:
    Whatever respond() returns.
  """
  _add_next_prev(request.patchset, request.patch)
  request.patch.nav_type = nav_type
  parsed_lines = patching.ParsePatchToLines(request.patch.lines)
  if parsed_lines is None:
    return HttpTextResponse('Can\'t parse the patch to lines', status=404)
  rows = engine.RenderUnifiedTableRows(request, parsed_lines)
  return respond(request, 'patch.html',
                 {'patch': request.patch,
                  'patchset': request.patchset,
                  'view_style': 'patch',
                  'rows': rows,
                  'issue': request.issue,
                  'context': _clean_int(request.GET.get('context'), -1),
                  'column_width': _clean_int(request.GET.get('column_width'),
                                             None),
                  'tab_spaces': _clean_int(request.GET.get('tab_spaces'), None),
                  })


@deco.access_control_allow_origin_star
@deco.image_required
@deco.require_methods('GET')
def image(request):
  """/<issue>/image/<patchset>/<patch>/<content> - Return patch's content."""
  response = HttpResponse(request.content.data, content_type=request.mime_type)
  filename = re.sub(
      r'[^\w\.]', '_', request.patch.filename.encode('ascii', 'replace'))
  response['Content-Disposition'] = 'attachment; filename="%s"' % filename
  response['Cache-Control'] = 'no-cache, no-store'
  return response


@deco.access_control_allow_origin_star
@deco.patch_required
@deco.require_methods('GET')
def download_patch(request):
  """/download/issue<issue>_<patchset>_<patch>.diff - Download patch."""
  return HttpTextResponse(request.patch.text)


def _issue_as_dict(issue, messages, request=None):
  """Converts an issue into a dict."""
  values = {
    'offer_cq': issue.is_cq_available,
    'owner': library.get_nickname(issue.owner, True, request),
    'owner_email': issue.owner.email(),
    'is_editor': issue.edit_allowed,
    'modified': str(issue.modified),
    'created': str(issue.created),
    'closed': issue.closed,
    'cc': issue.cc,
    'reviewers': issue.reviewers,
    'required_reviewers': issue.required_reviewers,
    'all_required_reviewers_approved': issue.all_required_reviewers_approved,
    'patchsets': [key.id() for key in issue.patchsets.iter(keys_only=True)],
    'description': issue.description,
    'subject': issue.subject,
    'project': issue.project,
    'issue': issue.key.id(),
    'base_url': issue.base,
    'target_ref': issue.target_ref,
    'private': issue.private,
    'commit': issue.commit,
    'cq_dry_run': issue.cq_dry_run,
    'cq_dry_run_last_triggered_by': issue.cq_dry_run_last_triggered_by,
    'landed_days_ago': issue.get_time_since_landed() or 'unknown',
  }
  if messages:
    values['messages'] = sorted(
      ({
        'sender': m.sender,
        'recipients': m.recipients,
        'date': str(m.date),
        'text': m.text,
        'approval': m.approval,
        'disapproval': m.disapproval,
        'auto_generated': m.auto_generated,
        'issue_was_closed': m.issue_was_closed,
        'patchset': m.patchset_key.id() if m.patchset_key else None,
      }
      for m in models.Message.query(ancestor=issue.key)),
      key=lambda x: x['date'])
  return values


def _patchset_as_dict(
    patchset, comments, try_jobs, request, swallow_exceptions=True):
  """Converts a patchset into a dict."""
  issue = patchset.issue_key.get()
  values = {
    'patchset': patchset.key.id(),
    'issue': issue.key.id(),
    'owner': library.get_nickname(issue.owner, True, request),
    'owner_email': issue.owner.email(),
    'message': patchset.message,
    'url': patchset.url,
    'created': str(patchset.created),
    'modified': str(patchset.modified),
    'num_comments': patchset.num_comments,
    'depends_on_patchset': patchset.depends_on_patchset,
    'dependent_patchsets': patchset.dependent_patchsets,
    'files': {},
  }
  if try_jobs:
    try_job_results = _get_patchset_try_job_results(
        patchset, swallow_exceptions=swallow_exceptions)
    values['try_job_results'] = [t.to_dict() for t in try_job_results]

  all_no_base_file_keys_future = models.Content.query(
      models.Content.file_too_large == True,
      ancestor=patchset.key).fetch_async(10000, keys_only=True, batch_size=1000)
  patches_future = models.Patch.query(ancestor=patchset.key).fetch_async(
      10000, batch_size=1000)

  all_comments_by_patch_id = {}
  if comments:
    comments = models.Comment.query(
        ancestor=patchset.key).order(models.Comment.date).fetch(
        10000, batch_size=1000)
    for comment in comments:
      patch_id_of_comment = comment.key.parent().id()
      if patch_id_of_comment not in all_comments_by_patch_id:
        all_comments_by_patch_id[patch_id_of_comment] = []
      all_comments_by_patch_id[patch_id_of_comment].append(comment)

  all_no_base_file_keys = set(all_no_base_file_keys_future.get_result())

  for patch in patches_future.get_result():
    # num_comments and num_drafts are left out for performance reason:
    # they cause a datastore query on first access. They could be added
    # optionally if the need ever arises.
    values['files'][patch.filename] = {
        'id': patch.key.id(),
        'is_binary': patch.is_binary,
        'no_base_file': patch.content_key in all_no_base_file_keys,
        'num_added': patch.num_added,
        'num_chunks': patch.num_chunks,
        'num_removed': patch.num_removed,
        'status': patch.status,
        'property_changes': '\n'.join(patch.property_changes),
    }
    if comments:
      visible_comments = []
      requester_email = request.user.email() if request.user else 'no email'
      comments_on_patch = all_comments_by_patch_id.get(patch.key.id(), [])
      for comment in comments_on_patch:
        if not comment or not comment.author:
          logging.info('Ignoring authorless comment: %r', comment)
          continue  # Ignore a small number of existing corrupt comments.
        if not comment.draft or requester_email == comment.author.email():
          visible_comments.append({
              'author': library.get_nickname(comment.author, True, request),
              'author_email': comment.author.email(),
              'date': str(comment.date),
              'lineno': comment.lineno,
              'text': comment.text,
              'left': comment.left,
              'draft': comment.draft,
              'message_id': comment.message_id,
              })

      values['files'][patch.filename]['messages'] = visible_comments

  return values


@deco.access_control_allow_origin_star
@deco.issue_required
@deco.json_response
@deco.require_methods('GET')
def api_issue(request):
  """/api/<issue> - Gets issue's data as a JSON-encoded dictionary."""
  messages = request.GET.get('messages', 'false').lower() == 'true'
  values = _issue_as_dict(request.issue, messages, request)
  return values

# pylint: disable=W0613
@deco.access_control_allow_origin_star
@deco.json_response
@deco.require_methods('GET')
def api_tryservers(request):
  """/api/tryservers - Gets tryservers as a JSON-encoded dictionary."""
  return models_chromium.TryserverBuilders.get_curated_tryservers()

@deco.access_control_allow_origin_star
@deco.patchset_required
@deco.json_response
@deco.require_methods('GET')
def api_patchset(request):
  """/api/<issue>/<patchset> - Gets an issue's patchset data as a JSON-encoded
  dictionary.
  """
  comments = request.GET.get('comments', 'false').lower() == 'true'
  try_jobs = request.GET.get('try_jobs', 'true').lower() == 'true'
  values = _patchset_as_dict(
      request.patchset, comments, try_jobs, request, swallow_exceptions=False)

  # Add the current datetime as seen by AppEngine (it should always be UTC).
  # This makes it possible to reliably compare try job timestamps (also based
  # on AppEngine time) and the current time, e.g. to determine how old the job
  # is.
  assert 'current_datetime' not in values
  values['current_datetime'] = str(datetime.datetime.now())

  return values

@deco.access_control_allow_origin_star
@deco.patchset_required
@deco.json_response
@deco.require_methods('GET')
def api_patchset_try_job_results(request):
  """/api/<issue>/<patchset>/try_job_results - Gets a patchset's try job
  results as a JSON-encoded list of dictionaries.
  """
  try_job_results = _get_patchset_try_job_results(
      request.patchset, swallow_exceptions=False)
  return [r.to_dict() for r in try_job_results]


def _get_context_for_user(request):
  """Returns the context setting for a user.

  The value is validated against models.CONTEXT_CHOICES.
  If an invalid value is found, the value is overwritten with
  django_settings.DEFAULT_CONTEXT.
  """
  get_param = request.GET.get('context') or None
  if 'context' in request.GET and get_param is None:
    # User wants to see whole file. No further processing is needed.
    return get_param
  if request.user:
    account = models.Account.current_user_account
    default_context = account.default_context
  else:
    default_context = django_settings.DEFAULT_CONTEXT
  context = _clean_int(get_param, default_context)
  if context is not None and context not in models.CONTEXT_CHOICES:
    context = django_settings.DEFAULT_CONTEXT
  return context

def _get_column_width_for_user(request):
  """Returns the column width setting for a user."""
  if request.user:
    account = models.Account.current_user_account
    default_column_width = account.default_column_width
  else:
    default_column_width = django_settings.DEFAULT_COLUMN_WIDTH
  column_width = _clean_int(request.GET.get('column_width'),
                            default_column_width,
                            django_settings.MIN_COLUMN_WIDTH,
                            django_settings.MAX_COLUMN_WIDTH)
  return column_width


def _get_tab_spaces_for_user(request):
  """Returns the tab spaces setting for a user."""
  if request.user:
    account = models.Account.current_user_account
    default_tab_spaces = account.default_tab_spaces
  else:
    default_tab_spaces = django_settings.DEFAULT_TAB_SPACES
  tab_spaces = _clean_int(request.GET.get('tab_spaces'),
                          default_tab_spaces,
                          django_settings.MIN_TAB_SPACES,
                          django_settings.MAX_TAB_SPACES)
  return tab_spaces


@deco.patch_filename_required
@deco.require_methods('GET')
def diff(request):
  """/<issue>/diff/<patchset>/<patch> - View a patch as a side-by-side diff"""
  if _use_new_ui(request):
    return _serve_new_ui(request)

  if request.patch.no_base_file:
    # Can't show side-by-side diff since we don't have the base file.  Show the
    # unified diff instead.
    return _patch_helper(request, 'diff')

  patchset = request.patchset
  patch = request.patch

  patchsets = list(request.issue.patchsets)

  context = _get_context_for_user(request)
  column_width = _get_column_width_for_user(request)
  tab_spaces = _get_tab_spaces_for_user(request)
  if patch.filename.startswith('webkit/api'):
    column_width = django_settings.MAX_COLUMN_WIDTH
    tab_spaces = django_settings.MAX_TAB_SPACES
  if patch.is_binary:
    rows = None
  else:
    try:
      rows = _get_diff_table_rows(request, patch, context, column_width,
                                  tab_spaces)
    except FetchError as err:
      return HttpTextResponse(str(err), status=404)

  _add_next_prev(patchset, patch)
  src_url = _map_base_url(request.issue.base)
  if src_url and not src_url.endswith('/'):
    src_url = src_url + '/'
  return respond(request, 'diff.html',
                 {'issue': request.issue,
                  'patchset': patchset,
                  'patch': patch,
                  'view_style': 'diff',
                  'rows': rows,
                  'context': context,
                  'context_values': models.CONTEXT_CHOICES,
                  'column_width': column_width,
                  'tab_spaces': tab_spaces,
                  'patchsets': patchsets,
                  'src_url': src_url,
                  })


def _get_diff_table_rows(request, patch, context, column_width, tab_spaces):
  """Helper function that returns rendered rows for a patch.

  Raises:
    FetchError if patch parsing or download of base files fails.
  """
  chunks = patching.ParsePatchToChunks(patch.lines, patch.filename)
  if chunks is None:
    raise FetchError('Can\'t parse the patch to chunks')

  # Possible FetchErrors are handled in diff() and diff_skipped_lines().
  content = request.patch.get_content()

  rows = list(engine.RenderDiffTableRows(request, content.lines,
                                         chunks, patch,
                                         context=context,
                                         colwidth=column_width,
                                         tabspaces=tab_spaces))
  return rows


@deco.patch_required
@deco.json_response
@deco.require_methods('GET')
def diff_skipped_lines(request, id_before, id_after, where, column_width,
                       tab_spaces=None):
  """/<issue>/diff/<patchset>/<patch> - Returns a fragment of skipped lines.

  *where* indicates which lines should be expanded:
    'b' - move marker line to bottom and expand above
    't' - move marker line to top and expand below
    'a' - expand all skipped lines
  """
  patch = request.patch
  if where == 'a':
    context = None
  else:
    context = _get_context_for_user(request) or 100

  column_width = _clean_int(column_width, django_settings.DEFAULT_COLUMN_WIDTH,
                            django_settings.MIN_COLUMN_WIDTH,
                            django_settings.MAX_COLUMN_WIDTH)
  tab_spaces = _clean_int(tab_spaces, django_settings.DEFAULT_TAB_SPACES,
                          django_settings.MIN_TAB_SPACES,
                          django_settings.MAX_TAB_SPACES)

  try:
    rows = _get_diff_table_rows(request, patch, None, column_width, tab_spaces)
  except FetchError as err:
    return HttpTextResponse('Error: %s; please report!' % err, status=500)
  return _get_skipped_lines_response(rows, id_before, id_after, where, context)


# there's no easy way to put a control character into a regex, so brute-force it
# this is all control characters except \r, \n, and \t
_badchars_re = re.compile(
    r'[\000\001\002\003\004\005\006\007\010\013\014\016\017'
    r'\020\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037]')


def _strip_invalid_xml(s):
  """Remove control chars other than \r\n\t from a string to be put in XML."""
  if _badchars_re.search(s):
    return ''.join(c for c in s if c >= ' ' or c in '\r\n\t')
  else:
    return s


def _get_skipped_lines_response(rows, id_before, id_after, where, context):
  """Helper function that returns response data for skipped lines"""
  response_rows = []
  id_before_start = int(id_before)
  id_after_end = int(id_after)
  if context is not None:
    id_before_end = id_before_start+context
    id_after_start = id_after_end-context
  else:
    id_before_end = id_after_start = None

  for row in rows:
    m = re.match('^<tr( name="hook")? id="pair-(?P<rowcount>\d+)">', row)
    if m:
      curr_id = int(m.groupdict().get("rowcount"))
      # expand below marker line
      if (where == 'b'
          and curr_id > id_after_start and curr_id <= id_after_end):
        response_rows.append(row)
      # expand above marker line
      elif (where == 't'
            and curr_id >= id_before_start and curr_id < id_before_end):
        response_rows.append(row)
      # expand all skipped lines
      elif (where == 'a'
            and curr_id >= id_before_start and curr_id <= id_after_end):
        response_rows.append(row)
      if context is not None and len(response_rows) >= 2*context:
        break

  # Create a usable structure for the JS part
  response = []
  response_rows =  [_strip_invalid_xml(r) for r in response_rows]
  dom = ElementTree.parse(StringIO('<div>%s</div>' % "".join(response_rows)))
  for node in dom.getroot().getchildren():
    content = [[x.items(), x.text] for x in node.getchildren()]
    response.append([node.items(), content])
  return response


def _get_diff2_data(request, ps_left_id, ps_right_id, patch_id, context,
                    column_width, tab_spaces, patch_filename=None):
  """Helper function that returns objects for diff2 views"""
  ps_left = models.PatchSet.get_by_id(int(ps_left_id), parent=request.issue.key)
  if ps_left is None:
    return HttpTextResponse(
        'No patch set exists with that id (%s)' % ps_left_id, status=404)
  ps_left.issue_key = request.issue.key
  ps_right = models.PatchSet.get_by_id(
    int(ps_right_id), parent=request.issue.key)
  if ps_right is None:
    return HttpTextResponse(
        'No patch set exists with that id (%s)' % ps_right_id, status=404)
  ps_right.issue_key = request.issue.key
  if patch_id is not None:
    patch_right = models.Patch.get_by_id(int(patch_id), parent=ps_right.key)
  else:
    patch_right = None
  if patch_right is not None:
    patch_right.patchset_key = ps_right.key
    if patch_filename is None:
      patch_filename = patch_right.filename
  # Now find the corresponding patch in ps_left
  patch_left = models.Patch.query(
      models.Patch.filename == patch_filename,
      ancestor=ps_left.key).get()

  if patch_left:
    try:
      new_content_left = patch_left.get_patched_content()
    except FetchError as err:
      return HttpTextResponse(str(err), status=404)
    lines_left = new_content_left.lines
  elif patch_right:
    lines_left = patch_right.get_content().lines
  else:
    lines_left = []

  if patch_right:
    try:
      new_content_right = patch_right.get_patched_content()
    except FetchError as err:
      return HttpTextResponse(str(err), status=404)
    lines_right = new_content_right.lines
  elif patch_left:
    lines_right = patch_left.get_content().lines
  else:
    lines_right = []

  rows = engine.RenderDiff2TableRows(request,
                                     lines_left, patch_left,
                                     lines_right, patch_right,
                                     context=context,
                                     colwidth=column_width,
                                     tabspaces=tab_spaces)
  rows = list(rows)
  if rows and rows[-1] is None:
    del rows[-1]

  return dict(patch_left=patch_left, patch_right=patch_right,
              ps_left=ps_left, ps_right=ps_right, rows=rows)


@deco.issue_required
@deco.require_methods('GET')
def diff2(request, ps_left_id, ps_right_id, patch_filename):
  """/<issue>/diff2/... - View the delta between two different patch sets."""
  context = _get_context_for_user(request)
  column_width = _get_column_width_for_user(request)
  tab_spaces = _get_tab_spaces_for_user(request)

  ps_right = models.PatchSet.get_by_id(
    int(ps_right_id), parent=request.issue.key)
  patch_right = None

  if ps_right:
    patch_right = models.Patch.query(
        models.Patch.filename == patch_filename,
        ancestor=ps_right.key).get()

  if patch_right:
    patch_id = patch_right.key.id()
  elif patch_filename.isdigit():
    # Perhaps it's an ID that's passed in, based on the old URL scheme.
    patch_id = int(patch_filename)
  else:  # patch doesn't exist in this patchset
    patch_id = None

  data = _get_diff2_data(request, ps_left_id, ps_right_id, patch_id, context,
                         column_width, tab_spaces, patch_filename)
  if isinstance(data, HttpResponse) and data.status_code != 302:
    return data

  patchsets = list(request.issue.patchsets)

  if data["patch_right"]:
    _add_next_prev2(data["ps_left"], data["ps_right"], data["patch_right"])
  return respond(request, 'diff2.html',
                 {'issue': request.issue,
                  'ps_left': data["ps_left"],
                  'patch_left': data["patch_left"],
                  'ps_right': data["ps_right"],
                  'patch_right': data["patch_right"],
                  'rows': data["rows"],
                  'patch_id': patch_id,
                  'context': context,
                  'context_values': models.CONTEXT_CHOICES,
                  'column_width': column_width,
                  'tab_spaces': tab_spaces,
                  'patchsets': patchsets,
                  'filename': patch_filename,
                  })


@deco.issue_required
@deco.json_response
@deco.require_methods('GET')
def diff2_skipped_lines(request, ps_left_id, ps_right_id, patch_id,
                        id_before, id_after, where, column_width,
                        tab_spaces=None):
  """/<issue>/diff2/... - Returns a fragment of skipped lines"""
  column_width = _clean_int(column_width, django_settings.DEFAULT_COLUMN_WIDTH,
                            django_settings.MIN_COLUMN_WIDTH,
                            django_settings.MAX_COLUMN_WIDTH)
  tab_spaces = _clean_int(tab_spaces, django_settings.DEFAULT_TAB_SPACES,
                          django_settings.MIN_TAB_SPACES,
                          django_settings.MAX_TAB_SPACES)

  if where == 'a':
    context = None
  else:
    context = _get_context_for_user(request) or 100

  data = _get_diff2_data(request, ps_left_id, ps_right_id, patch_id, 10000,
                         column_width, tab_spaces)
  if isinstance(data, HttpResponse) and data.status_code != 302:
    return data
  return _get_skipped_lines_response(data["rows"], id_before, id_after,
                                     where, context)


def _get_comment_counts(account, patchset):
  """Helper to get comment counts for all patches in a single query.

  The helper returns two dictionaries comments_by_patch and
  drafts_by_patch with patch key as key and comment count as
  value. Patches without comments or drafts are not present in those
  dictionaries.
  """
  # A key-only query won't work because we need to fetch the patch key
  # in the for loop further down.
  comment_query = models.Comment.query(ancestor=patchset.key)

  # Get all comment counts with one query rather than one per patch.
  comments_by_patch = {}
  drafts_by_patch = {}
  for c in comment_query:
    pkey = c.patch_key
    if not c.draft:
      comments_by_patch[pkey] = comments_by_patch.setdefault(pkey, 0) + 1
    elif account and c.author == account.user:
      drafts_by_patch[pkey] = drafts_by_patch.setdefault(pkey, 0) + 1

  return comments_by_patch, drafts_by_patch


def _add_next_prev(patchset, patch):
  """Helper to add .next and .prev attributes to a patch object."""
  patch.prev = patch.next = None
  patches = list(patchset.patches)
  patchset.patches_cache = patches  # Required to render the jump to select.

  comments_by_patch, drafts_by_patch = _get_comment_counts(
     models.Account.current_user_account, patchset)

  last_patch = None
  next_patch = None
  last_patch_with_comment = None
  next_patch_with_comment = None

  found_patch = False
  for p in patches:
    if p.filename == patch.filename:
      found_patch = True
      continue

    p._num_comments = comments_by_patch.get(p.key, 0)
    p._num_drafts = drafts_by_patch.get(p.key, 0)

    if not found_patch:
      last_patch = p
      if p.num_comments > 0 or p.num_drafts > 0:
        last_patch_with_comment = p
    else:
      if next_patch is None:
        next_patch = p
      if p.num_comments > 0 or p.num_drafts > 0:
        next_patch_with_comment = p
        # safe to stop scanning now because the next with out a comment
        # will already have been filled in by some earlier patch
        break

  patch.prev = last_patch
  patch.next = next_patch
  patch.prev_with_comment = last_patch_with_comment
  patch.next_with_comment = next_patch_with_comment


def _add_next_prev2(ps_left, ps_right, patch_right):
  """Helper to add .next and .prev attributes to a patch object."""
  patch_right.prev = patch_right.next = None
  patches = list(ps_right.patches)
  ps_right.patches_cache = patches  # Required to render the jump to select.

  n_comments, n_drafts = _get_comment_counts(
    models.Account.current_user_account, ps_right)

  last_patch = None
  next_patch = None
  last_patch_with_comment = None
  next_patch_with_comment = None

  found_patch = False
  for p in patches:
    if p.filename == patch_right.filename:
      found_patch = True
      continue

    p._num_comments = n_comments.get(p.key, 0)
    p._num_drafts = n_drafts.get(p.key, 0)

    if not found_patch:
      last_patch = p
      if ((p.num_comments > 0 or p.num_drafts > 0) and
          ps_left.key.id() in p.delta):
        last_patch_with_comment = p
    else:
      if next_patch is None:
        next_patch = p
      if ((p.num_comments > 0 or p.num_drafts > 0) and
          ps_left.key.id() in p.delta):
        next_patch_with_comment = p
        # safe to stop scanning now because the next with out a comment
        # will already have been filled in by some earlier patch
        break

  patch_right.prev = last_patch
  patch_right.next = next_patch
  patch_right.prev_with_comment = last_patch_with_comment
  patch_right.next_with_comment = next_patch_with_comment


@deco.login_required
@deco.issue_required
@deco.require_methods('GET')
def draft_message(request):
  """/<issue>/draft_message - Retrieve draft messages."""
  query = models.Message.query(
      models.Message.sender == request.user.email(),
      models.Message.draft == True,
      ancestor=request.issue.key)
  if query.count() == 0:
    draft_message = None
  else:
    draft_message = query.get()
  if request.method == 'GET':
    return HttpTextResponse(draft_message.text if draft_message else '')
  return HttpTextResponse('An error occurred.', status=500)


@deco.access_control_allow_origin_star
@deco.json_response
@deco.require_methods('GET', 'POST')
def search(request):
  """/search - Search for issues or patchset.

  Returns HTTP 500 if the corresponding index is missing.
  """
  if request.method == 'GET':
    if _use_new_ui(request) and request.GET.get('format') != 'json':
      return _serve_new_ui(request)
    form = SearchForm(request.GET)
    if not form.is_valid() or not request.GET:
      return respond(request, 'search.html', {'form': form})
  else:
    form = SearchForm(request.POST)
    if not form.is_valid():
      return HttpTextResponse('Invalid arguments', status=400)
  logging.info('%s' % form.cleaned_data)
  keys_only = form.cleaned_data['keys_only'] or False
  requested_format = form.cleaned_data['format'] or 'html'
  limit = form.cleaned_data['limit']
  with_messages = form.cleaned_data['with_messages']
  if requested_format == 'html':
    keys_only = False
    limit = limit or DEFAULT_LIMIT
  else:
    if not limit:
      if keys_only:
        # It's a fast query.
        limit = 1000
      elif with_messages:
        # It's an heavy query.
        limit = 10
      else:
        limit = 100

  # This uses eventual consistency and cannot be made strongly consistent.
  q = models.Issue.query(default_options=ndb.QueryOptions(keys_only=keys_only))
  encoded_cursor = form.cleaned_data['cursor'] or None
  if encoded_cursor:
    cursor = datastore_query.Cursor(urlsafe=encoded_cursor)
  else:
    cursor = None

  if form.cleaned_data['closed'] is not None:
    q = q.filter(models.Issue.closed == form.cleaned_data['closed'])
  if form.cleaned_data['owner']:
    q = q.filter(models.Issue.owner == form.cleaned_data['owner'])
  if form.cleaned_data['reviewer']:
    q = q.filter(models.Issue.reviewers == form.cleaned_data['reviewer'])
  if form.cleaned_data['cc']:
    q = q.filter(models.Issue.cc == form.cleaned_data['cc'])
  if form.cleaned_data['private'] is not None:
    q = q.filter(models.Issue.private == form.cleaned_data['private'])
  if form.cleaned_data['commit'] is not None:
    q = q.filter(models.Issue.commit == form.cleaned_data['commit'])
  if form.cleaned_data['repo_guid']:
    q = q.filter(models.Issue.repo_guid == form.cleaned_data['repo_guid'])
  if form.cleaned_data['base']:
    q = q.filter(models.Issue.base == form.cleaned_data['base'])
  if form.cleaned_data['project']:
    q = q.filter(models.Issue.project == form.cleaned_data['project'])

  # Calculate a default value depending on the query parameter.
  # Prefer sorting by modified date over created date and showing
  # newest first over oldest.
  default_sort = '-modified'
  if form.cleaned_data['created_after']:
    q = q.filter(models.Issue.created >= form.cleaned_data['created_after'])
    default_sort = 'created'
  if form.cleaned_data['modified_after']:
    q = q.filter(models.Issue.modified >= form.cleaned_data['modified_after'])
    default_sort = 'modified'
  if form.cleaned_data['created_before']:
    q = q.filter(models.Issue.created < form.cleaned_data['created_before'])
    default_sort = '-created'
  if form.cleaned_data['modified_before']:
    q = q.filter(models.Issue.modified < form.cleaned_data['modified_before'])
    default_sort = '-modified'

  sorted_by = form.cleaned_data['order'] or default_sort
  direction = (
    datastore_query.PropertyOrder.DESCENDING
    if sorted_by.startswith('-') else datastore_query.PropertyOrder.ASCENDING)
  q = q.order(datastore_query.PropertyOrder(sorted_by.lstrip('-'), direction))

  # Update the cursor value in the result.
  if requested_format == 'html':
    nav_params = dict(
        (k, v) for k, v in form.cleaned_data.iteritems() if v is not None)
    return _paginate_issues_with_cursor(
        reverse(search),
        request,
        q,
        cursor,
        limit,
        'search_results.html',
        extra_nav_parameters=nav_params)

  # We do not simply use fetch_page() because we do some post-filtering which
  # could lead to under-filled pages.   Instead, we iterate, filter and keep
  # going until we have enough post-filtered results, then return those along
  # with the cursor after the last item.
  filtered_results = []
  next_cursor = None
  query_iter = q.iter(start_cursor=cursor, produce_cursors=True)

  for result in query_iter:
    if keys_only:
      # There's not enough information to filter. The only thing that is leaked
      # is the issue's key.
      filtered_results.append(result)
    elif result.view_allowed:
      filtered_results.append(result)

    if len(filtered_results) >= limit:
      break

  # If any results are returned, also include a cursor to try to get more.
  if filtered_results:
    next_cursor = query_iter.cursor_after()

  data = {
    'cursor': next_cursor.urlsafe() if next_cursor else '',
  }
  if keys_only:
    data['results'] = [i.id() for i in filtered_results]
  else:
    data['results'] = [_issue_as_dict(i, with_messages, request)
                      for i in filtered_results]
  return data


### User Profiles ###


@deco.login_required
@deco.xsrf_required
@deco.require_methods('GET', 'POST')
def settings(request):
  account = models.Account.current_user_account

  if request.method != 'POST':
    if _use_new_ui(request):
      return _serve_new_ui(request)

    nickname = account.nickname
    default_context = account.default_context
    default_column_width = account.default_column_width
    default_tab_spaces = account.default_tab_spaces
    form = SettingsForm(initial={
        'nickname': nickname,
        'context': default_context,
        'column_width': default_column_width,
        'deprecated_ui': account.deprecated_ui,
        'tab_spaces': default_tab_spaces,
        'notify_by_email': account.notify_by_email,
        'notify_by_chat': account.notify_by_chat,
        'add_plus_role': account.add_plus_role,
        'display_generated_msgs':
            account.display_generated_msgs,
        'display_exp_tryjob_results':
            account.display_exp_tryjob_results,
        'send_from_email_addr': account.send_from_email_addr,
        })
    return respond(request, 'settings.html', {'form': form})
  form = SettingsForm(request.POST)
  if form.is_valid():
    account.nickname = form.cleaned_data.get('nickname')
    account.default_context = form.cleaned_data.get('context')
    account.default_column_width = form.cleaned_data.get('column_width')
    account.deprecated_ui = form.cleaned_data.get('deprecated_ui')
    account.default_tab_spaces = form.cleaned_data.get('tab_spaces')
    account.notify_by_email = form.cleaned_data.get('notify_by_email')
    account.notify_by_chat = form.cleaned_data.get('notify_by_chat')
    account.add_plus_role = form.cleaned_data.get('add_plus_role')
    account.display_generated_msgs = form.cleaned_data.get(
        'display_generated_msgs')
    account.display_exp_tryjob_results = form.cleaned_data.get(
        'display_exp_tryjob_results')
    account.send_from_email_addr = form.cleaned_data.get('send_from_email_addr')

    account.fresh = False
    account.put()
  else:
    return respond(request, 'settings.html', {'form': form})
  return HttpResponseRedirect(reverse(index))


@deco.login_required
@deco.json_response
@deco.require_methods('GET')
def api_settings(_request):
  """Repond with user prefs in JSON."""
  account = models.Account.current_user_account
  return {
    'xsrf_token': account.get_xsrf_token(),
    'email': account.email,
    'nickname': account.nickname,
    'deprecated_ui': account.deprecated_ui,
    'default_context': account.default_context,
    'default_column_width': account.default_column_width,
    'default_tab_spaces': account.default_tab_spaces,
    'notify_by_email': account.notify_by_email,
    'notify_by_chat': account.notify_by_chat,
    'add_plus_role': account.add_plus_role,
    'display_generated_msgs': account.display_generated_msgs,
    'display_exp_tryjob_results': account.display_exp_tryjob_results,
    'send_from_email_addr': account.send_from_email_addr,
    }


@deco.require_methods('POST')
@deco.login_required
@deco.xsrf_required
def account_delete(_request):
  account = models.Account.current_user_account
  account.key.delete()
  return HttpResponseRedirect(users.create_logout_url(reverse(index)))


@deco.user_key_required
@deco.require_methods('GET')
def user_popup(request):
  """/user_popup - Pop up to show the user info."""
  try:
    return _user_popup(request)
  except Exception as err:
    logging.exception('Exception in user_popup processing:')
    # Return HttpResponse because the JS part expects a 200 status code.
    return HttpHtmlResponse(
        '<font color="red">Error: %s; please report!</font>' %
        err.__class__.__name__)


def _user_popup(request):
  user = request.user_to_show
  popup_html = memcache.get('user_popup:' + user.email())
  if popup_html is None:
    # These use eventual consistency and cannot be made strongly consistent.
    num_issues_created = models.Issue.query(
        models.Issue.closed == False, models.Issue.owner == user).count()
    num_issues_reviewed = models.Issue.query(
        models.Issue.closed == False,
      models.Issue.reviewers == user.email()).count()

    user.nickname = models.Account.get_nickname_for_email(user.email())
    popup_html = render_to_response('user_popup.html',
                            {'user': user,
                             'num_issues_created': num_issues_created,
                             'num_issues_reviewed': num_issues_reviewed,
                             },
                             context_instance=RequestContext(request))
    # Use time expired cache because the number of issues will change over time
    memcache.add('user_popup:' + user.email(), popup_html, 60)
  return popup_html


@deco.login_required
@deco.require_methods('GET')
def xsrf_token(request):
  """/xsrf_token - Return the user's XSRF token.

  This is used by tools like git-cl that need to be able to interact with the
  site on the user's behalf.  A custom header named X-Requesting-XSRF-Token must
  be included in the HTTP request; an error is returned otherwise.
  """
  if not request.META.has_key('HTTP_X_REQUESTING_XSRF_TOKEN'):
    return HttpTextResponse(
        'Please include a header named X-Requesting-XSRF-Token '
        '(its content doesn\'t matter).',
        status=400)
  return HttpTextResponse(models.Account.current_user_account.get_xsrf_token())


@deco.task_queue_required('deltacalculation')
@deco.require_methods('POST')
def task_calculate_delta(request):
  """/restricted/tasks/calculate_delta - Calculate deltas for a patchset.

  This URL is called by taskqueue to calculate deltas behind the
  scenes. Returning a HttpResponse with any 2xx status means that the
  task was finished successfully. Raising an exception means that the
  taskqueue will retry to run the task.
  """
  ps_key = request.POST.get('key')
  if not ps_key:
    logging.error('No patchset key given.')
    return HttpResponse()
  try:
    patchset = ndb.Key(urlsafe=ps_key).get()
  except (db.KindError, db.BadKeyError) as err:
    logging.error('Invalid PatchSet key %r: %s' % (ps_key, err))
    return HttpResponse()
  if patchset is None:  # e.g. PatchSet was deleted inbetween
    logging.error('Missing PatchSet key %r' % ps_key)
    return HttpResponse()
  patchset.calculate_deltas()
  return HttpResponse()


def _build_state_value(django_request, user):
  """Composes the value for the 'state' parameter.

  Packs the current request URI and an XSRF token into an opaque string that
  can be passed to the authentication server via the 'state' parameter.

  Meant to be similar to oauth2client.appengine._build_state_value.

  Args:
    django_request: Django HttpRequest object, The request.
    user: google.appengine.api.users.User, The current user.

  Returns:
    The state value as a string.
  """
  relative_path = django_request.get_full_path().encode('utf-8')
  uri = django_request.build_absolute_uri(relative_path)
  token = xsrfutil.generate_token(xsrf_secret_key(), user.user_id(),
                                  action_id=str(uri))
  return  uri + ':' + token


def _create_flow(django_request):
  """Create the Flow object.

  The Flow is calculated using mostly fixed values and constants retrieved
  from other modules.

  Args:
    django_request: Django HttpRequest object, The request.

  Returns:
    oauth2client.client.OAuth2WebServerFlow object.
  """
  redirect_path = reverse(oauth2callback)
  redirect_uri = django_request.build_absolute_uri(redirect_path)
  client_id, client_secret, _, _ = auth_utils.SecretKey.get_config()
  return OAuth2WebServerFlow(client_id, client_secret, auth_utils.EMAIL_SCOPE,
                             redirect_uri=redirect_uri,
                             approval_prompt='force')


def _validate_port(port_value):
  """Makes sure the port value is valid and can be used by a non-root user.

  Args:
    port_value: Integer or string version of integer.

  Returns:
    Integer version of port_value if valid, otherwise None.
  """
  try:
    port_value = int(port_value)
  except (ValueError, TypeError):
    return None

  if not (1024 <= port_value <= 49151):
    return None

  return port_value


@deco.login_required
@deco.require_methods('GET')
def get_access_token(request):
  """/get-access-token - Facilitates OAuth 2.0 dance for client.

  Meant to take a 'port' query parameter and redirect to localhost with that
  port and the user's access token appended.
  """
  user = request.user
  flow = _create_flow(request)

  flow.params['state'] = _build_state_value(request, user)
  credentials = StorageByKeyName(
      CredentialsNDBModel, user.user_id(), 'credentials').get()

  authorize_url = flow.step1_get_authorize_url()
  redirect_response_object = HttpResponseRedirect(authorize_url)
  if credentials is None or credentials.invalid:
    return redirect_response_object

  # Find out if credentials is expired
  refresh_failed = False
  if credentials.access_token is None or credentials.access_token_expired:
    try:
      credentials.refresh(httplib2.Http())
    except AccessTokenRefreshError:
      return redirect_response_object
    except Exception:
      refresh_failed = True

  port_value = _validate_port(request.GET.get('port'))
  if port_value is None:
    return HttpTextResponse('Access Token: %s' % (credentials.access_token,))

  # Send access token along to localhost client
  redirect_template_args = {'port': port_value}
  if refresh_failed:
    quoted_error = urllib.quote(OAUTH_DEFAULT_ERROR_MESSAGE)
    redirect_template_args['error'] = quoted_error
    client_uri = ACCESS_TOKEN_FAIL_REDIRECT_TEMPLATE % redirect_template_args
  else:
    quoted_access_token = urllib.quote(credentials.access_token)
    redirect_template_args['token'] = quoted_access_token
    client_uri = ACCESS_TOKEN_REDIRECT_TEMPLATE % redirect_template_args

  return HttpResponseRedirect(client_uri)


@deco.login_required
@deco.require_methods('GET')
def oauth2callback(request):
  """/oauth2callback - Callback handler for OAuth 2.0 redirect.

  Handles redirect and moves forward to the rest of the application.
  """
  error = request.GET.get('error')
  if error:
    error_msg = request.GET.get('error_description', error)
    return HttpTextResponse(
        'The authorization request failed: %s' % _safe_html(error_msg))
  else:
    user = request.user
    flow = _create_flow(request)
    credentials = flow.step2_exchange(request.GET)
    StorageByKeyName(
        CredentialsNDBModel, user.user_id(), 'credentials').put(credentials)
    redirect_uri = _parse_state_value(str(request.GET.get('state')),
                                      user)
    return HttpResponseRedirect(redirect_uri)


@deco.admin_required
@deco.require_methods('GET', 'POST')
def set_client_id_and_secret(request):
  """/restricted/set-client-id-and-secret - Allows admin to set Client ID and
  Secret.

  These values, from the Google APIs console, are required to validate
  OAuth 2.0 tokens within auth_utils.py.
  """
  if request.method == 'POST':
    form = ClientIDAndSecretForm(request.POST)
    if form.is_valid():
      client_id = form.cleaned_data['client_id']
      client_secret = form.cleaned_data['client_secret']
      additional_client_ids = form.cleaned_data['additional_client_ids']
      whitelisted_emails = form.cleaned_data['whitelisted_emails']
      logging.info('Adding client_id: %s' % client_id)
      auth_utils.SecretKey.set_config(client_id, client_secret,
                                      additional_client_ids,
                                      whitelisted_emails)
    else:
      logging.info('Form is invalid')
    return HttpResponseRedirect(reverse(set_client_id_and_secret))
  else:
    client_id, client_secret, additional_client_ids, whitelisted_emails = \
      auth_utils.SecretKey.get_config()
    form = ClientIDAndSecretForm(initial={
      'client_id': client_id,
      'client_secret': client_secret,
      'additional_client_ids': additional_client_ids,
      'whitelisted_emails': whitelisted_emails})
    return respond(request, 'set_client_id_and_secret.html', {'form': form})
