# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Profile reporting service."""

import datetime
import json
import logging

from google.appengine.ext import db
from google.appengine.ext import webapp

from appengine_module.chromium_status.base_page import BasePage
from appengine_module.chromium_status import utils


class ProfileReport(db.Model):
  timestamp = db.DateTimeProperty(auto_now_add=True)
  executable = db.StringProperty()
  first_arg = db.StringProperty()
  argv = db.TextProperty()
  platform = db.StringProperty()
  domain = db.StringProperty()
  duration = db.FloatProperty()

  @staticmethod
  def create(**kwargs):
    """Creates a new ProfileReport.

    Calculates executable and first_arg from argv.
    """
    arg0 = kwargs['argv'].split(' ', 1)[0]
    kwargs['executable'] = arg0.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    commands = kwargs['argv'].split(' ', 2)
    if len(commands) >= 2:
      kwargs['first_arg'] = commands[1]
    return ProfileReport(**kwargs)


class Profiling(BasePage):
  @utils.requires_write_access
  def get(self):
    """Returns json formated data according to the provided filters."""
    limit = int(self.request.get('limit', 100))
    accepted_filters = ('executable', 'first_arg', 'platform', 'domain')
    reports = ProfileReport.all()
    min_duration = self.request.get('min_duration')
    max_duration = self.request.get('max_duration')
    includes_not = False
    for key in accepted_filters:
      value = self.request.get(key)
      if value:
        if value.startswith('!'):
          reports.filter('%s !=' % key, value[1:])
          includes_not = True
        else:
          reports.filter('%s =' % key, value)
    if min_duration:
      reports.filter('duration >=', float(min_duration))
    if max_duration:
      reports.filter('duration <=', float(max_duration))
    if not includes_not:
      if min_duration or max_duration:
        # Otherwise it'll throw a BadArgumentError.
        reports.order('-duration')
      else:
        reports.order('-timestamp')
      # Otherwise, gives up, the DB can't sort when a inequality filter property
      # is specified.

    data = [report.AsDict() for report in reports.fetch(limit=limit)]
    self.response.headers.add_header('content-type', 'application/json')
    self.response.headers.add_header('Access-Control-Allow-Origin', '*')
    # Write it as compact as possible.
    self.response.out.write(json.dumps(data, separators=(',',':')))

  def post(self):
    """Adds a new profile report.

    Anyone can add a report.
    """
    blacklist = ('timestamp', 'executable', 'first_arg')
    required = ('argv', 'duration', 'platform', 'domain')
    accepted_keys = list(set(ProfileReport.properties()) - set(blacklist))
    arguments = self.request.arguments()
    kwargs = dict(
        (k, self.request.get(k)) for k in accepted_keys if k in arguments)

    if not all(kwargs.get(k, None) for k in required):
      logging.info('missing required keys. %r' % kwargs)
      self.response.out.write('fail')
      return

    try:
      kwargs['duration'] = float(kwargs['duration'])
    except ValueError:
      logging.info('duration(%s) is invalid' % kwargs['duration'])
      self.response.out.write('fail')
      return

    report = ProfileReport.create(**kwargs)
    report.put()
    logging.debug('%s on %s took %.1f' % (
        report.executable, report.platform, report.duration))
    self.response.out.write('OK.')


class Cleanup(webapp.RequestHandler):
  """A cron job."""
  @utils.requires_work_queue_login
  def get(self):
    """Delete reports older than ~6 months."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=31*6)
    # Will only delete 1000 reports at a time max. Shouldn't be a problem unless
    # we get more than 1000 reports/day.
    for report in db.Query(ProfileReport, keys_only=True).filter(
        'date <', cutoff):
      db.delete(report)
