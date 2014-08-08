# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
import hashlib
import logging
import os
import urllib

import webapp2
from webapp2_extras import jinja2

from google.appengine.api import app_identity
from google.appengine.api import users
from google.appengine.ext import deferred

import controller  # pylint: disable=W0403


class BaseHandler(webapp2.RequestHandler):
  """Provide a cached Jinja environment to each request."""

  def __init__(self, *args, **kwargs):
    webapp2.RequestHandler.__init__(self, *args, **kwargs)

  @staticmethod
  def jinja2_factory(app):
    template_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'templates'))
    config = {'template_path': template_dir}
    jinja = jinja2.Jinja2(app, config=config)
    jinja.environment.globals.update({
      'sha256': hashlib.sha256,
      'quote': urllib.quote,
      'len': len,
      'enumerate': enumerate,
      'range': range,
    })
    return jinja

  @webapp2.cached_property
  def jinja2(self):
    # Returns a Jinja2 renderer cached in the app registry.
    return jinja2.get_jinja2(app=self.app, factory=BaseHandler.jinja2_factory)

  def render_response(self, _template, **context):
    # Renders a template and writes the result to the response.
    rv = self.jinja2.render_template(_template, **context)
    self.response.write(rv)


class StepView(BaseHandler):  # pragma: no cover
  def get(self, *args):
    context = {'title': 'Chrome Infra Stats'}

    user =  users.get_current_user()
    if user:
      context['login_text'] = 'logged in as %s' % user.email()
    else:
      context['login_text'] = 'login'
      context['login_url'] = users.create_login_url(self.request.uri)

    group_data = OrderedDict()
    step_url = '%s://%s/_ah/api/stats/v1/aggregate/%s?limit=100' % (
        self.request.scheme,
        app_identity.get_default_version_hostname(),
        args[0])
    step_name = args[0]
    if len(args) == 3:
      step_url += '&builder=%s' % args[2]
      step_name = '%s/%s' % (args[2], args[0])
    if len(args) >= 2:
      step_url += '&master=%s' % args[1]
      step_name = '%s/%s' % (args[1], step_name)

    group_data[step_name] = step_url

    context['group_data'] = group_data

    context['column_tuples'] = [
        [('Median', 'median'),
         ('75th', 'seventyfive'),
         ('90th', 'ninety'),
         ('99th', 'ninetynine'),
         ('Max', 'maximum'),
         ('Mean', 'mean'),
         ('Std Dev', 'stddev')],
        [('Count', 'count'),
        ('Failure Count', 'failure_count'),
        ('Failure Rate', 'failure_rate')],
    ]

    self.render_response('step_list.html', **context)


class StartPage(BaseHandler):  # pragma: no cover
  def get(self):
    self.response.out.write('started')


class MainPage(BaseHandler):
  def get(self):
    context = {'title': 'Chrome Infra Stats'}

    user =  users.get_current_user()
    if user:  # pragma: no cover
      context['login_text'] = 'logged in as %s' % user.email()
    else:
      context['login_text'] = 'login'
      context['login_url'] = users.create_login_url(self.request.uri)

    context['masters'] = controller.masters
    context['steps'] = controller.get_worth_it_steps()
    context['hour_window'] = controller.WORTH_IT_HOUR_WINDOW

    self.render_response('main.html', **context)


class Masters(BaseHandler):  # pragma: no cover
  def get(self):
    context = {'title': 'Chrome Infra Stats'}

    user =  users.get_current_user()
    if user:
      context['login_text'] = 'logged in as %s' % user.email()
    else:
      context['login_text'] = 'login'
      context['login_url'] = users.create_login_url(self.request.uri)

    context['masters'] = controller.masters

    self.render_response('masters.html', **context)


class CrawlMasters(BaseHandler):  # pragma: no cover
  def get(self):
    controller.process_all_masters()
    self.response.out.write('getting data')


class RunStepSummary(BaseHandler):  # pragma: no cover
  def get(self, *args):
    if len(args) == 1:
      controller.get_step_summary(args[0])
      self.response.out.write('ran step query on %s' % args[0])
    elif len(args) == 2:
      controller.get_step_summary_for_master(args[0], args[1])
      self.response.out.write('ran master-step query on %s-%s' % (
        args[0], args[1]))
    elif len(args) == 3:
      controller.get_step_summary_for_builder(args[0], args[1], args[2])
      self.response.out.write('ran master-builder-step query on %s-%s-%s' % (
        args[0], args[1], args[2]))
    else:
      self.abort(400)


class RunStepSummaryJobs(BaseHandler):  # pragma: no cover
  def get(self):
    controller.generate_step_summaries()
    self.response.out.write('ran query')


class DeleteStepSummary(BaseHandler):  # pragma: no cover
  def get(self, step):
    deferred.defer(
        controller.delete_step_records, step, _queue='summary-delete',
        _target='stats-backend')
    self.response.out.write('deleted %s' % step)


class DeleteAllStepSummaries(BaseHandler):  # pragma: no cover
  def get(self):
    deferred.defer(controller.delete_all_step_records, _queue='summary-delete',
        _target='stats-backend')
    self.response.out.write('deleted all')


class CachePage(BaseHandler):  # pragma: no cover
  def get(self):
    deferred.defer(controller.get_cleaned_steps, disable_cache_lookup=True,
        _queue='step-operations', _target='stats-backend')
    deferred.defer(controller.get_worth_it_steps, disable_cache_lookup=True,
        _queue='step-operations', _target='stats-backend')
    self.response.out.write('cleaned_steps cached')


class CacheSteps(BaseHandler):  # pragma: no cover
  def get(self):
    deferred.defer(controller.get_steps, disable_cache_lookup=True,
        _queue='step-operations', _target='stats-backend')
    self.response.out.write('steps cached')


class GetStepsForHour(BaseHandler):  # pragma: no cover
  def get(self, step, time):
    context = {'title': 'Chrome Infra Stats'}

    user =  users.get_current_user()
    if user:
      context['login_text'] = 'logged in as %s' % user.email()
    else:
      context['login_text'] = 'login'
      context['login_url'] = users.create_login_url(self.request.uri)

    try:
      hour = datetime.strptime(time, '%Y-%m-%d:%H')
    except ValueError as e:
      logging.info('Parse error: %s' % str(e))
      self.abort(400)
    context['step'] = step
    context['stats'] = controller.get_step_records_for_hour(step, hour)
    end = hour + timedelta(hours=1)
    context['records'] = controller.get_step_record_iterator(step, hour, end)
    controller.get_step_records_for_hour(step, hour)

    self.render_response('step_records.html', **context)


class CullOldSteps(BaseHandler):  # pragma: no cover
  def get(self):
    deferred.defer(controller.step_cleanup, _queue='step-operations',
    _target='stats-backend')
    self.response.out.write('steps cleaned')
