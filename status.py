# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Status management pages."""

import datetime
import re

import simplejson as json
from google.appengine.api import memcache
from google.appengine.ext import db

from base_page import BasePage
import utils


class Status(db.Model):
  """Description for the status table."""
  # The username who added this status.
  username = db.StringProperty(required=True)
  # The date when the status got added.
  date = db.DateTimeProperty(auto_now_add=True)
  # The message. It can contain html code.
  message = db.StringProperty(required=True)


def GeneralState(message):
  """Interpret tree status from message in one place.

  NOTE: please keep all interpretation of tree message here!
  Args:
    message: human input status message.
  Returns:
    String representing the general state.
  """
  closed = re.search('close', message, re.IGNORECASE)
  if closed and re.search('maint', message, re.IGNORECASE):
    return 'maintenance'
  if re.search('throt', message, re.IGNORECASE):
    return 'throttled'
  if closed:
    return 'closed'
  return 'open'


def CanCommitFreely(message):
  return GeneralState(message) == 'open'


def StatusToDict(status, as_json=False):
  st = status.AsDict()
  st['general_state'] = GeneralState(status.message)
  st['can_commit_freely'] = CanCommitFreely(status.message)
  if not as_json:
    st['date'] = status.date  # Preserve date-y-ness
  return st


class AllStatusPage(BasePage):
  """Displays a big chunk, 1500, status values."""
  def get(self):
    query = db.Query(Status).order('-date')
    start_date = self.request.get('startTime')
    if start_date != "":
      query.filter('date <',
                   datetime.datetime.utcfromtimestamp(int(start_date)))

    end_date = self.request.get('endTime')
    beyond_end_of_range_status = None
    if end_date != "":
      end_date = datetime.datetime.utcfromtimestamp(int(end_date))
      query.filter('date >=', end_date)
      # We also need to get the very next status in the range, otherwise
      # the caller can't tell what the effective tree status was at time
      # |end_date|.
      beyond_end_of_range_status = Status.gql(
          'WHERE date < :end_date ORDER BY date DESC LIMIT 1',
          end_date=end_date).get()

    # It's not really an html page.
    self.response.headers['Content-Type'] = 'text/plain'
    template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
    template_values['status'] = (StatusToDict(s, False) for s in query)
    template_values['beyond_end_of_range_status'] = beyond_end_of_range_status
    self.DisplayTemplate('allstatus.html', template_values)


class CurrentPage(BasePage):
  """Displays the /current page."""

  def get(self):
    """Displays the current message and nothing else."""
    # Module 'google.appengine.api.memcache' has no 'get' member
    # pylint: disable=E1101
    out_format = self.request.get('format', 'html')
    status = memcache.get('last_status')
    if status is None:
      status = Status.gql('ORDER BY date DESC').get()
      # Cache 2 seconds.
      memcache.add('last_status', status, 2)
    if not status:
      self.error(501)
    elif out_format == 'raw':
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(status.message)
    elif out_format == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.headers['Access-Control-Allow-Origin'] = '*'
      data = json.dumps(StatusToDict(status, True))
      callback = self.request.get('callback')
      if callback:
        if re.match(r'^[a-zA-Z$_][a-zA-Z$0-9._]*$', callback):
          data = '%s(%s);' % (callback, data)
      self.response.out.write(data)
    elif out_format == 'html':
      template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
      template_values['message'] = status.message
      template_values['state'] = GeneralState(status.message)
      self.DisplayTemplate('current.html', template_values, use_cache=True)
    else:
      self.error(400)


class StatusPage(BasePage):
  """Displays the /status page."""

  def get(self):
    """Displays 1 if the tree is open, and 0 if the tree is closed."""
    status = Status.gql('ORDER BY date DESC').get()
    if status:
      if CanCommitFreely(status.message):
        message_value = '1'
      else:
        message_value = '0'

      self.response.headers['Cache-Control'] =  'no-cache, private, max-age=0'
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(message_value)

  @utils.admin_only
  def post(self):
    """Adds a new message from a backdoor.

    The main difference with MainPage.post() is that it doesn't look for
    conflicts and doesn't redirect to /.
    """
    message = self.request.get('message')
    username = self.request.get('username')
    if message and username:
      status = Status(message=message, username=username)
      status.put()
      # Cache the status.
      # Module 'google.appengine.api.memcache' has no 'set' member
      # pylint: disable=E1101
      memcache.set('last_status', status)
    self.response.out.write('OK')


class StatusViewerPage(BasePage):
  """Displays the /status_viewer page."""

  def get(self):
    """Displays status_viewer.html template."""
    template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
    self.DisplayTemplate('status_viewer.html', template_values)


class MainPage(BasePage):
  """Displays the main page containing the last 100 messages."""

  @utils.require_user
  def get(self, error_message='', last_message=''):
    """Sets the information to be displayed on the main page."""
    status = Status.gql('ORDER BY date DESC LIMIT 25')
    current_status = status.get()
    if not last_message and current_status:
      last_message = current_status.message

    template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
    template_values['status'] = (StatusToDict(s, False) for s in status)
    template_values['message'] = last_message
    # If the DB is empty, current_status is None.
    if current_status:
      template_values['last_status_key'] = current_status.key()
    template_values['error_message'] = error_message
    self.DisplayTemplate('main.html', template_values)

  @utils.require_user
  @utils.admin_only
  def post(self):
    """Adds a new message."""
    # We pass these variables back into get(), prepare them.
    last_message = ''
    error_message = ''

    # Get the posted information.
    new_message = self.request.get('message')
    last_status_key = self.request.get('last_status_key')
    if new_message:
      current_status = Status.gql('ORDER BY date DESC').get()
      if current_status and (last_status_key != str(current_status.key())):
        error_message = ('Message not saved, mid-air collision detected, '
                         'please resolve any conflicts and try again!')
        last_message = new_message
      else:
        status = Status(message=new_message, username=self.user.email())
        status.put()
        # Cache the status.
        # Module 'google.appengine.api.memcache' has no 'set' member
        # pylint: disable=E1101
        memcache.set('last_status', status)

    self.get(error_message, last_message)


def bootstrap():
  if db.GqlQuery('SELECT __key__ FROM Status').get() is None:
    Status(username='none', message='welcome to status').put()
