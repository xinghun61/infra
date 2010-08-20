# Copyright (c) 2008-2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Status management pages."""

import datetime
import os
import re
import wsgiref.handlers

from django.utils import simplejson as json
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from base_page import BasePage


class Status(db.Model):
  """Description for the status table."""
  # The username who added this status.
  username = db.StringProperty(required=True)
  # The date when the status got added.
  date = db.DateTimeProperty(auto_now_add=True)
  # The message. It can contain html code.
  message = db.StringProperty(required=True)


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

    template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
    template_values['status'] = query
    template_values['beyond_end_of_range_status'] = beyond_end_of_range_status
    self.DisplayTemplate('allstatus.html', template_values)


class CurrentPage(BasePage):
  """Displays the /current page."""

  def get(self):
    """Displays the current message and nothing else."""
    format = self.request.get('format', 'html')
    status = memcache.get('last_status')
    if status is None:
      status = Status.gql('ORDER BY date DESC').get()
      # Cache 2 seconds.
      memcache.add('last_status', status, 2)
    if not status:
      self.error(501)
    elif format == 'raw':
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(status.message)
    elif format == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.out.write(json.dumps(status.AsDict()))
    elif format == 'html':
      template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
      template_values['message'] = status.message
      self.DisplayTemplate('current.html', template_values, use_cache=True)
    else:
      self.error(400)


class StatusPage(BasePage):
  """Displays the /status page."""

  def get(self):
    """Displays 1 if the tree is open, and 0 if the tree is closed."""
    status = Status.gql('ORDER BY date DESC').get()
    if status:
      is_closed = re.compile("closed", re.IGNORECASE)
      if is_closed.search(status.message):
        message_value = '0'
      else:
        message_value = '1'

      self.response.headers['Cache-Control'] =  'no-cache, private, max-age=0'
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write(message_value)

  def post(self):
    """Adds a new message from a backdoor."""
    # Get the posted information.
    (validated, is_admin) = self.ValidateUser()
    if not validated:
      return
    message = self.request.get('message')
    username = self.request.get('username')
    if message and username:
      status = Status(message=message, username=username)
      status.put()
    self.redirect('/')


class StatusViewerPage(BasePage):
  """Displays the /status_viewer page."""

  def get(self):
    """Displays status_viewer.html template."""
    template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
    self.DisplayTemplate('status_viewer.html', template_values)


class MainPage(BasePage):
  """Displays the main page containing the last 100 messages."""

  def get(self):
    """Sets the information to be displayed on the main page."""
    (validated, is_admin) = self.ValidateUser()
    if not validated:
      return

    status = Status.gql('ORDER BY date DESC LIMIT 25')
    last_status = status.get()
    last_message = ''
    if last_status:
      last_message = last_status.message

    template_values = self.InitializeTemplate(self.app_name + ' Tree Status')
    template_values['status'] = status
    template_values['is_admin'] = is_admin
    template_values['last_message'] = last_message
    self.DisplayTemplate('main.html', template_values)

  def post(self):
    """Adds a new message."""
    (validated, is_admin) = self.ValidateUser()
    if not validated or not is_admin:
      return

    # Get the posted information.
    message = self.request.get('message')
    if message:
      user = self.GetCurrentUser()
      if not user or not user.email():
        self.response.out.write(
            '<html><body>Failed to retrieve your email address to update '
            'the tree status. Please try signing in first</body></html>')
        self.error(403)
        return
      status = Status(message=message,
                      username=self.GetCurrentUser().email())
      status.put()

    self.get()
