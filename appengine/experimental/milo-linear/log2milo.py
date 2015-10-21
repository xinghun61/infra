# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Log2milo."""

import logging
import sys
import json

from annotator import MatchAnnotation

import json
import endpoints
import os
import sys
import webapp2
import urllib
import logging

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from google.appengine.ext import ndb
from google.appengine.api import memcache
from google.appengine.api import urlfetch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import ereporter2
from components import utils
from components import auth

VERSION_ID = os.environ['CURRENT_VERSION_ID']


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


class Thing(object):
  def __init__(self, name):
    self.name =  name
    self.log = []
    self.log_lines = []
    self.closed = False
    self.started = False
    self.step_text = ''

  def get_log_line(self, name):
    for log_line in self.log_lines:
      if log_line.name == name:
        return log_line
    log_line = Thing(name)
    self.log_lines.append(log_line)
    return log_line

  def add_line(self, line):
    self.log.append(line)

  def serialize(self):
    return {
        'name': self.name,
        'log': self.log,
        'log_lines': [ll.serialize() for ll in self.log_lines],
        'step_text': self.step_text
    }


class LogParser(object):
  def __init__(self):
    self.cursor = None
    self.steps = []
    self.props = {}

  def get_step(self, step_name):
    for step in self.steps:
      if step.name == step_name:
        return step
    step = Thing(step_name)
    self.steps.append(step)

  def STEP_CURSOR(self, step_name):
    self.cursor = self.get_step(step_name)

  def STEP_CLOSED(self):
    if self.cursor.closed:
      raise Exception('Step %s already closed' % self.cursor.name)
    if not self.cursor.started:
      raise Exception('Trying to close %s, but not started' % self.cursor.name)
    self.cursor.closed = True

  def HONOR_ZERO_RETURN_CODE(self):
    pass

  def SEED_STEP(self, step_name):
    self.get_step(step_name)

  def STEP_STARTED(self):
    self.cursor.started = True

  def STEP_LOG_LINE(self, log, line):
    self.cursor.get_log_line(log).add_line(line)

  def STEP_LOG_END(self, log):
    self.cursor.get_log_line(log).closed = True

  def STEP_TEXT(self, text):
    self.cursor.step_text += text

  def SET_BUILD_PROPERTY(self, k, v):
    self.props[k] = json.loads(v)

  def add_line(self, line):
    self.cursor.add_line(line)

  def get_result(self):
    return ([step.serialize() for step in self.steps], self.props)

  def ready(self):
    return self.cursor and self.cursor.started and not self.cursor.closed


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument('target')


def run(log):
  parser = LogParser()
  for line in log.splitlines():
    if line.startswith('@@@') and line.endswith('@@@') and len(line) > 6:
      MatchAnnotation(line, parser)
    elif parser.ready():
      parser.add_line(line)
  return parser.get_result()


class ExecRequest(messages.Message):
  swarming_id = messages.StringField(1, required=True)


class Property(messages.Message):
  key = messages.StringField(1, required=True)
  value = messages.StringField(2)


class ExecResponse(messages.Message):
  properties = messages.MessageField(Property, 1, repeated=True)
  steps = messages.StringField(2)  # JSON blob.


@auth.endpoints_api(
    name='log', version='v1',
    title='Swarming Log API')
class LogApi(remote.Service):
  @auth.endpoints_method(
      ExecRequest,
      ExecResponse,
      path='swarming/{swarming_id}',
      http_method='GET',
      name='get_log'
  )
  def get_log(self, exec_request):
    swarming_url = (
        'https://chromium-swarm-dev.appspot.com/swarming/api/v1/'
        'client/task/%s/output/0' % exec_request.swarming_id)
    logging.info('Fetching %s' % swarming_url)
    resp = urlfetch.fetch(
        swarming_url, follow_redirects=False, validate_certificate=True)
    if resp.status_code != 200:
      logging.error('Expected 200, got %s' % resp.status_code)
      raise Exception()
    logging.debug('log: %s' % resp.content)
    json_log = json.loads(resp.content)
    log = json_log['output']
    steps, props = run(log)
    response_props = [
        Property(key=k, value=v) for k, v in sorted(props.iteritems())]
    return ExecResponse(properties=response_props, steps=json.dumps(steps))



