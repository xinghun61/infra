# Copyright (c) 2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Error reporting service, aka Breakpad for Python."""

import datetime

from django.utils import simplejson as json

from google.appengine.api import users
from google.appengine.api import xmpp
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp

from base_page import BasePage
from utils import work_queue_only


class Report(db.Model):
  date = db.DateTimeProperty(auto_now_add=True)
  user = db.StringProperty()
  stack = db.TextProperty()
  args = db.TextProperty()
  exception = db.TextProperty()
  host = db.StringProperty()

  def asDict(self):
    return {
        'date': self.date.isoformat(),
        'user': self.user,
        'stack': self.stack,
        'args': self.args,
        'exception': self.exception,
        'host': self.host,
    }


class Admins(db.Model):
  user = db.UserProperty()
  # When set to 0, doesn't sent IMs.
  nb_lines = db.IntegerProperty(default=5)


class BreakPad(BasePage):
  def get(self):
    (validated, is_admin) = self.ValidateUser()
    if not is_admin:
      self.response.set_status(401)
      return

    limit = int(self.request.get('limit', 10))
    reports = Report.gql('ORDER BY date DESC LIMIT %d' % limit)
    if self.request.get('json'):
      data = [report.asDict() for report in reports]
      self.response.headers.add_header("content-type", 'text/plain')
      self.response.out.write(json.dumps(data, indent=2, sort_keys=True))
    else:
      page_value = {'reports': reports}
      template_values = self.InitializeTemplate('Breakpad reports')
      template_values.update(page_value)
      self.DisplayTemplate('breakpad.html', template_values)

  def post(self):
    """Adds a new breakpad report."""
    user = self.request.get('user')
    stack = self.request.get('stack')
    args = self.request.get('args')
    exception = self.request.get('exception')
    host = self.request.get('host')
    if user and stack and args:
      Report(user=user, stack=stack, args=args, exception=exception, host=host
          ).put()
      params = {'user': user, 'stack': stack}
      taskqueue.add(url='/restricted/breakpad/im', params=params)
    self.response.out.write('A stack trace has been sent to the maintainers.')


class SendIM(webapp.RequestHandler):
  """A taskqueue."""
  @work_queue_only
  def post(self):
    user = self.request.get('user')
    stack = self.request.get('stack')
    stacks = stack.split('\n')
    for i in Admins.all():
      if not i.nb_lines or not i.user or not i.user.email():
        continue
      stack_text = '\n'.join(stacks[-min(len(stacks), i.nb_lines):])
      text = '%s:\n%s' % (user, stack_text)
      xmpp.send_message(i.user.email(), text)


class Cleanup(webapp.RequestHandler):
  """A cron job."""
  @work_queue_only
  def get(self):
    """Delete reports older than 31 days."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=31)
    # Will only delete 1000 reports at a time max. Shouldn't be a problem unles
    # we get more than 1000 reports/day. I hope not!
    for report in db.Query(Report, keys_only=True).filter('date <', cutoff):
      db.delete(report)


class SetData(BasePage):
  """Quick and dirty schema creator. Kept for historical purposes."""
  @work_queue_only
  def get(self):
    if self.ValidateUser()[1]:
      Admins(user=users.get_current_user()).put()
