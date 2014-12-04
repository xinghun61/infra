# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Error reporting service, aka Breakpad for Python."""

import datetime
import json

from google.appengine.api import taskqueue
from google.appengine.api import xmpp
from google.appengine.ext import db
from google.appengine.ext import webapp

from appengine_module.chromium_status.base_page import BasePage
from appengine_module.chromium_status import utils


class Report(db.Model):
  date = db.DateTimeProperty(auto_now_add=True)
  user = db.StringProperty()
  stack = db.TextProperty()
  args = db.TextProperty()
  exception = db.TextProperty()
  host = db.StringProperty()
  cwd = db.StringProperty()
  version = db.StringProperty(multiline=True)

  def asDict(self):
    return {
        'date': self.date.isoformat(),
        'user': self.user,
        'stack': self.stack,
        'args': self.args,
        'exception': self.exception,
        'host': self.host,
        'cwd': self.cwd,
        'version': self.version,
    }


class Admins(db.Model):
  user = db.UserProperty()
  # When set to 0, doesn't sent IMs.
  nb_lines = db.IntegerProperty(default=5)


class BreakPad(BasePage):
  @utils.requires_write_access
  def get(self):
    limit = int(self.request.get('limit', 30))
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
    """Adds a new breakpad report.

    Anyone can add a stack trace.
    """
    user = self.request.get('user')
    stack = self.request.get('stack')
    args = self.request.get('args')
    exception = self.request.get('exception')
    host = self.request.get('host')
    cwd = self.request.get('cwd')
    version = self.request.get('version')
    # Cheap blacklisting to keep me sane.
    if ('twisted.spread.pb.DeadReferenceError: Calling Stale Broker' in
        exception):
      self.response.out.write('Ignored.')
      return
    if user and stack and args:
      Report(user=user, stack=stack, args=args, exception=exception, host=host,
             cwd=cwd, version=version).put()
      params = {'user': user, 'stack': stack}
      taskqueue.add(url='/restricted/breakpad/im', params=params)
    self.response.out.write('A stack trace has been sent to the maintainers.')


class SendIM(webapp.RequestHandler):
  """A taskqueue."""
  @utils.requires_work_queue_login
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
  @utils.requires_work_queue_login
  def get(self):
    """Delete reports older than 31 days."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=31)
    # Will only delete 1000 reports at a time max. Shouldn't be a problem unles
    # we get more than 1000 reports/day. I hope not!
    for report in db.Query(Report, keys_only=True).filter('date <', cutoff):
      db.delete(report)


def bootstrap():
  if db.GqlQuery('SELECT __key__ FROM Admins').get() is None:
    # Insert a dummy Admins so it can be edited through the admin console
    Admins().put()
