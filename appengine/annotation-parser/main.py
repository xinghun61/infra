# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import collections
import datetime
import json
import logging
import os
import re

from google.appengine.api import app_identity
from google.appengine.api import urlfetch

import jinja2
import webapp2


JINJA_ENV = jinja2.Environment(
  loader=jinja2.FileSystemLoader(
      os.path.join(os.path.dirname(__file__), 'templates')),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)


REGEX_STEP_CURSOR = re.compile(r'^@@@STEP_CURSOR[@ ](.+)@@@$')


Property = collections.namedtuple('Property', ['name', 'value', 'source'])


Log = collections.namedtuple('Log', ['name', 'link'])


class Step(object):
  def __init__(self, task_id, name):
    self._task_id = task_id
    self.name = name

    self.css_class = 'success'

    self.link = '#'

    self.logs = [
      Log(name='stdio', link='/swarming/step/%s/%s' % (
          task_id, base64.urlsafe_b64encode(self.name))),
    ]

  def fail(self):
    self.css_class = 'failure'

  def get(self, _name, default=None):
    return default


def fetch_json(url):
  logging.info('Fetching %s' % url)
  authorization_token, _ = app_identity.get_access_token(
      'https://www.googleapis.com/auth/userinfo.email')
  response = urlfetch.fetch(
      url, follow_redirects=False, validate_certificate=True,
      headers={'Authorization': 'Bearer ' + authorization_token})
  logging.debug(response.content)
  # TODO(phajdan.jr): Handle responses other than HTTP 200.
  return json.loads(response.content)


def fetch_swarming_task_metadata(task_id):
  return fetch_json(
      'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/'
      'task/%s/result' % task_id)


def fetch_swarming_task_output(task_id):
  return fetch_json(
      'https://chromium-swarm.appspot.com/_ah/api/swarming/v1/'
      'task/%s/stdout' % task_id)


def parse_datetime(datetime_string):
  return datetime.datetime.strptime(datetime_string, '%Y-%m-%dT%H:%M:%S.%f')


def access_allowed(task_metadata):
  # TODO(phajdan.jr): Remove the user-specific logic when no longer needed.
  if task_metadata.get('user') == 'phajdan@google.com':
    return True

  if 'allow_milo:1' in task_metadata.get('tags', []):
    return True

  return False


class SwarmingBuildHandler(webapp2.RequestHandler):
  def get(self, task_id):
    task_metadata = fetch_swarming_task_metadata(task_id)

    if not access_allowed(task_metadata):
      self.abort(403)

    data = fetch_swarming_task_output(task_id)

    steps = []
    seen_steps = set()
    last_step = None
    for line in data['output'].splitlines():
      if line == '@@@STEP_FAILURE@@@' and last_step:
        last_step.fail()
        continue

      match = REGEX_STEP_CURSOR.match(line)
      if not match:
        continue
      step_name = match.group(1)

      if step_name in seen_steps:
        continue
      seen_steps.add(step_name)

      last_step = Step(task_id, step_name)
      steps.append(last_step)

    started_ts = parse_datetime(task_metadata['started_ts'])
    completed_ts = parse_datetime(task_metadata['completed_ts'])

    properties = []
    for key in ('task_id', 'user', 'bot_id'):
      properties.append(Property(
          name=key, value=task_metadata[key], source='swarming'))
    for dimension in task_metadata['bot_dimensions']:
      properties.append(Property(
          name=dimension['key'],
          value=json.dumps(dimension['value']),
          source='swarming dimensions'))

    build_success = ((not task_metadata['failure']) and
                     (not task_metadata['internal_failure']))

    build_result = ['Build successful'] if build_success else ['Failed']

    template_values = {
      'stylesheet': '/static/default.css',

      'build_id': task_metadata['task_id'],
      'result_css': 'success' if build_success else 'failure',
      'build_result': build_result,

      'slave_url': ('https://chromium-swarm.appspot.com/restricted/bot/%s' %
                    task_metadata['bot_id']),
      'slavename': task_metadata['bot_id'],

      'steps': steps,

      'properties': properties,

      'start': task_metadata['started_ts'],
      'end': task_metadata['completed_ts'],
      'elapsed': str(completed_ts - started_ts),
    }

    template = JINJA_ENV.get_template('build.html')
    self.response.write(template.render(template_values))


class SwarmingStepHandler(webapp2.RequestHandler):
  def get(self, task_id, step_id_base64):
    task_metadata = fetch_swarming_task_metadata(task_id)

    if not access_allowed(task_metadata):
      self.abort(403)

    step_id = base64.urlsafe_b64decode(step_id_base64)

    self.response.headers['Content-Type'] = 'text/plain'

    data = fetch_swarming_task_output(task_id)

    inside_step = False
    step_lines = []
    for line in data['output'].splitlines():
      if inside_step:
        if line == '@@@STEP_CLOSED@@@':
          break
        step_lines.append(line)
      elif line in ['@@@STEP_CURSOR@%s@@@' % step_id,
                    '@@@STEP_CURSOR %s@@@' % step_id]:
        inside_step = True

    self.response.write('\n'.join(step_lines))


app = webapp2.WSGIApplication([
    (r'/swarming/build/(.+)', SwarmingBuildHandler),
    (r'/swarming/step/(.+)/(.+)', SwarmingStepHandler),
])
