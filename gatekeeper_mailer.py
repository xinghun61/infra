#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides mailer templates for gatekeeper_ng.

This module populates jinja mail templates to notify tree watchers when the
tree is closed.
"""

import jinja2
import os
import utils

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    autoescape=True)
jinja_environment.filters['urlquote'] = utils.urlquote

# From buildbot's results.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY = range(6)
Results = ["success", "warnings", "failure", "skipped", "exception", "retry"]


class MailTemplate(object):
  """Encapsulates a buildbot status email."""

  status_header = 'Automatically closing tree for "%(steps)s" on "%(builder)s"'
  default_subject = ('buildbot %(result)s in %(projectName)s on %(builder)s, '
                     'revision %(revision)s')

  def __init__(self, waterfall_url, build_url, project_name, fromaddr,
               reply_to=None, subject=None):


    self.reply_to = reply_to
    self.fromaddr = fromaddr
    self.subject = subject or self.default_subject
    self.waterfall_url = waterfall_url
    self.build_url = build_url
    self.project_name = project_name

  def genMessageContent(self, build_status):
    builder_name = build_status['builderName']
    us_steps = ','.join(build_status['unsatisfied'])
    revisions_list = build_status['revisions']
    status_text = self.status_header % {
        'builder': builder_name,
        'steps': us_steps,
    }

    # Use the first line as a title.
    status_title = status_text.split('\n', 1)[0]
    blame_list = ','.join(build_status['blamelist'])
    revisions_string = ''
    latest_revision = 0
    if revisions_list:
      revisions_string = ', '.join([str(rev) for rev in revisions_list])
      latest_revision = max([rev for rev in revisions_list])
    if build_status['result'] == FAILURE:
      result = 'failure'
    else:
      result = 'warning'

    context = {
        'status_title': status_title,
        'waterfall_url': self.waterfall_url,
        'status': status_text.replace('\n', "<br>\n"),
        'build_url': self.build_url,
        'revisions': revisions_string,
        'blame_list': blame_list,
        'build_status': build_status,
        'builder_name': builder_name,
    }

    html_content = jinja_environment.get_template('waterfall_mail.html').render(
        context)

    text_content = jinja_environment.get_template('mail_text.txt').render(
        context)

    subject = self.subject % {
        'result': result,
        'projectName': self.project_name,
        'builder': builder_name,
        'reason': build_status['reason'],
        'revision': str(latest_revision),
        'buildnumber': str(build_status['number']),
    }

    return text_content, html_content, subject
