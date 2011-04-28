# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Profile reporting service."""

import datetime
import logging

import simplejson as json

from google.appengine.ext import db
from google.appengine.ext import webapp

from base_page import BasePage
import utils


class ProfileReport(db.Model):
  timestamp = db.DateTimeProperty(auto_now_add=True)
  executable = db.StringProperty()
  first_arg = db.StringProperty()
  argv = db.TextProperty()
  platform = db.StringProperty()
  duration = db.FloatProperty()

  def asDict(self):
    return {
        'timestamp': self.timestamp.isoformat(),
        'executable': self.executable,
        'first_arg': self.first_arg,
        'argv': self.argv,
        'platform': self.platform,
        'duration': self.duration,
    }


class Profiling(BasePage):
  @utils.admin_only
  def get(self):
    limit = int(self.request.get('limit', 100))
    executable = self.request.get('executable')
    first_arg = self.request.get('first_arg')
    platform = self.request.get('platform')
    reports = ProfileReport.all()
    reports.order('-timestamp')
    if executable:
      reports.filter('executable =', executable)
    if first_arg:
      reports.filter('first_arg =', first_arg)
    if platform:
      reports.filter('platform =', platform)
    data = [report.asDict() for report in reports.fetch(limit=limit)]
    self.response.headers.add_header('content-type', 'application/json')
    # Write it as compact as possible.
    self.response.out.write(json.dumps(data, separators=(',',':')))

  def post(self):
    """Adds a new profile report.

    Anyone can add a report.
    """
    argv = self.request.get('argv')
    duration = self.request.get('duration')
    platform = self.request.get('platform')
    try:
      duration = float(duration)
    except ValueError:
      logging.info('duration(%s) is invalid' % duration)
      duration = None
    if not argv or not duration or not platform:
      logging.info('argv(%s) or duration(%s) or platform(%s) is invalid.' % (
        argv, duration, platform))
      self.response.out.write('FAIL')
      return

    executable = argv.split(' ', 1)[0].rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    commands = argv.split(' ', 2)
    first_arg = None
    if len(commands) >= 2:
      first_arg = commands[1]
    ProfileReport(
        executable=executable,
        first_arg=first_arg,
        argv=argv,
        platform=platform,
        duration=duration).put()
    logging.debug('%s on %s took %.1f' % (executable, platform, duration))
    self.response.out.write('OK.')


class Cleanup(webapp.RequestHandler):
  """A cron job."""
  @utils.work_queue_only
  def get(self):
    """Delete reports older than ~6 months."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=31*6)
    # Will only delete 1000 reports at a time max. Shouldn't be a problem unless
    # we get more than 1000 reports/day.
    for report in db.Query(ProfileReport, keys_only=True).filter(
        'date <', cutoff):
      db.delete(report)
