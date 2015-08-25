# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

from google.appengine.api import users

import jinja2
import webapp2

from components import decorators
from components import template

import docs

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
template.bootstrap({'doc': TEMPLATES_DIR})


class MainHandler(webapp2.RequestHandler):
  """Main page"""

  def get(self):
    query = self.request.get('q')

    user = users.get_current_user()
    data = {
      'query': query,
      'error': None,
      'search_results': [],
      'user': {
        'email': user.email() if user else None,
        'login_url': users.create_login_url(),
        'logout_url': users.create_logout_url('/'),
      }
    }
    is_googler = user and user.email().endswith('@google.com')

    if query:
      try:
        data['search_results'] = list(
            docs.find(query, include_internal=is_googler))
      except Exception as ex:
        logging.exception('Exception during search for "%s"', query)
        data['error'] = ex.message
        self.response.set_status(500)

    self.response.write(template.render('doc/index.html', data))


class CrawlHandler(webapp2.RequestHandler):
  """Updates search index."""
  @decorators.require_cronjob
  def get(self):
    docs.cron_crawl()


def get_frontend_routes():  # pragma: no cover
  return [
      webapp2.Route('/', MainHandler),
  ]


def get_backend_routes():
  return [
      webapp2.Route(
          r'/internal/cron/docsearch/crawl',
          CrawlHandler),
      # webapp2.Route(
      #     docs.UPDATE_DOCS_TASK_URL,
      #     UpdateDocsHandler),
  ]
