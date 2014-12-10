# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import appengine_config

import datetime
import json
import logging
import os.path
import pickle
import sys
import urllib

sys.path.append(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), 'third_party'))

from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import webapp
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
import cloudstorage

import app
import gtest_parser

# pylint: disable=pointless-string-statement
"""When displaying a list of results, how many to display on one page."""
PAGE_SIZE = 100


def _clean_int(value, default):
  """Convert a value to an int, or the default value if conversion fails."""
  try:
    return int(value)
  except (TypeError, ValueError), _:
    return default


class MyRequestHandler(webapp.RequestHandler):
  """Base request handler with this application specific helpers."""

  def _render_template(self, name, values):
    """
    Wrapper for template.render that updates response
    and knows where to look for templates.
    """
    self.response.out.write(template.render(
        os.path.join(os.path.dirname(__file__), 'templates', name),
        values))


class StatusReceiverAction(MyRequestHandler):

  def post(self):
    # This handler should be extremely fast so that buildbot doesn't fail
    # the push and doesn't get stuck on us. Defer all processing to the
    # background.
    try:
      deferred.defer(app.process_status_push, self.request.body, _queue='fast')
    except Exception:
      # For large requests we have to do it now. We can't return HTTP 500
      # because buildbot will try again.
      app.process_status_push(self.request.body)


class FetchBuildersAction(MyRequestHandler):

  def get(self):
    deferred.defer(app.fetch_builders)


class FetchStepsAction(MyRequestHandler):

  def get(self):
    deferred.defer(app.fetch_steps)


class UpdateParsedDataAction(MyRequestHandler):

  def get(self):
    query = app.BuildStep.all(keys_only=True)
    query.filter('is_fetched =', True)
    query.filter('is_too_large =', False)
    deferred.defer(app.for_all_entities,
                   query,
                   app.update_parsed_data,
                   None)


class MainAction(MyRequestHandler):

  def get(self):
    self._render_template('main.html', {})


class GTestQueryAction(MyRequestHandler):

  def get(self):
    gtest_results = []
    cursor = None
    if self.request.get('gtest_query'):
      query = app.GTestResult.all()
      query.filter('fullname =', self.request.get('gtest_query'))
      query.order('-time_finished')
      if self.request.get('cursor'):
        query.with_cursor(start_cursor=self.request.get('cursor'))
      gtest_results = query.fetch(PAGE_SIZE)
      cursor = query.cursor()
    self._render_template('query.html', {
        'gtest_query': self.request.get('gtest_query'),
        'cursor': cursor,
        'gtest_results': gtest_results,
    })


class SuppressionQueryAction(MyRequestHandler):

  def get(self):
    query = app.MemorySuppressionResult.all()
    query.filter('name =', self.request.get('suppression_query'))
    query.order('-time_finished')
    if self.request.get('cursor'):
      query.with_cursor(start_cursor=self.request.get('cursor'))
    suppression_results = query.fetch(PAGE_SIZE)
    self._render_template('suppression_query.html', {
        'suppression_query': self.request.get('suppression_query'),
        'cursor': query.cursor(),
        'suppression_results': suppression_results,
    })


class UnusedSuppressionsAction(MyRequestHandler):

  def post(self):
    now_timestamp = datetime.datetime.now()
    queries = []
    for line in self.request.body.splitlines():
      query = app.MemorySuppressionResult.all()
      query.filter('name =', line)
      query.order('-time_finished')
      queries.append(query.run(limit=1))

    for q in queries:
      for sr in q:
        if now_timestamp - sr.time_finished > datetime.timedelta(days=30):
          self.response.out.write(sr.name + '\n')


class ListAction(MyRequestHandler):
  """Lists stored build results."""

  def get(self):
    all_steps = app.BuildStep.all().order('-time_finished')
    if self.request.get('buildbot_root'):
      all_steps.filter('buildbot_root =',
                       urllib.unquote(self.request.get('buildbot_root')))
    if self.request.get('builder'):
      all_steps.filter('builder =',
                       urllib.unquote(self.request.get('builder')))
    if self.request.get('step_name'):
      all_steps.filter('step_name =',
                       urllib.unquote(self.request.get('step_name')))
    if self.request.get('status'):
      all_steps.filter('status =', _clean_int(urllib.unquote(
          self.request.get('status')), None))

    if self.request.get('cursor'):
      all_steps.with_cursor(start_cursor=self.request.get('cursor'))

    steps = all_steps.fetch(limit=PAGE_SIZE)
    step_names = app.iterate_large_result(app.StepName.all().order('name'))

    self._render_template('list.html', {
        'buildbot_roots': app.BUILDBOT_ROOTS,
        'step_names': step_names,
        'steps': steps,
        'cursor': all_steps.cursor(),
        'filter_buildbot_root': self.request.get('buildbot_root', ''),
        'filter_builder': self.request.get('builder', ''),
        'filter_step_name': self.request.get('step_name', ''),
        'filter_status': self.request.get('status', ''),
        })


class BuildStepJSONAction(MyRequestHandler):
  def get(self):
    all_steps = app.BuildStep.all().order('-time_finished')

    if self.request.get('cursor'):
      all_steps.with_cursor(start_cursor=self.request.get('cursor'))

    build_steps = all_steps.fetch(limit=1000)

    json_data = {
      'build_steps': [
        {
          'build_number': bs.build_number,
          'buildbot_root': bs.buildbot_root,
          'builder': bs.builder,
          'status': bs.status,
          'step_number': bs.step_number,
          'step_name': bs.step_name,
          # BigQuery doesn't recognize the T separator, but space works.
          'time_started': bs.time_started.isoformat(sep=' '),
          'time_finished': bs.time_finished.isoformat(sep=' '),
        } for bs in build_steps
      ],
      'cursor': all_steps.cursor(),
    }

    self.response.out.write(json.dumps(json_data))


class SuppressionSummaryAction(MyRequestHandler):
  """Displays summary information about memory suppressions."""

  def get(self):
    sort = 'count'
    if self.request.get('sort') in ('count',):
      sort = self.request.get('sort')
    query = app.MemorySuppressionSummary.all()
    monthly_timestamp = datetime.date.today().replace(day=1)
    query.filter('monthly_timestamp =', monthly_timestamp)
    query.order('monthly_timestamp')
    query.order('-%s' % sort)
    if self.request.get('cursor'):
      query.with_cursor(start_cursor=self.request.get('cursor'))
    suppression_summaries = query.fetch(PAGE_SIZE)
    self._render_template('suppression_summary.html', {
        'suppression_summary_query':
            self.request.get('suppression_summary_query'),
        'suppression_summaries': suppression_summaries,
        'cursor': query.cursor(),
        'sort': sort,
    })


class ViewRawLogAction(blobstore_handlers.BlobstoreDownloadHandler):
  """Sends selected log file to the user."""

  def get(self, blobkey): # pylint: disable=arguments-differ
    blob_info = blobstore.BlobInfo.get(urllib.unquote(blobkey))
    if not blob_info:
      self.error(404)
      return
    self.send_blob(blob_info)


application = webapp.WSGIApplication(
  [('/', MainAction),
   ('/gtest_query', GTestQueryAction),
   ('/suppression_query', SuppressionQueryAction),
   ('/suppression_summary', SuppressionSummaryAction),
   ('/unused_suppressions', UnusedSuppressionsAction),
   ('/list', ListAction),
   ('/build_step_json', BuildStepJSONAction),
   ('/status_receiver', StatusReceiverAction),
   ('/tasks/fetch_builders', FetchBuildersAction),
   ('/tasks/fetch_steps', FetchStepsAction),
   ('/tasks/update_parsed_data', UpdateParsedDataAction),
   ('/viewlog/raw/(.*)', ViewRawLogAction)])


def main():
  my_default_retry_params = cloudstorage.RetryParams(
      initial_delay=0.5,
      max_delay=30.0,
      backoff_factor=2,
      urlfetch_timeout=60)
  cloudstorage.set_default_retry_params(my_default_retry_params)

  run_wsgi_app(application)


if __name__ == '__main__':
  main()
