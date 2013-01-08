# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""StatusPush handler from the buildbot master.

See event_sample.txt for event format examples.
"""

import datetime
import json
import logging
import time

from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext.db import polymodel
from google.appengine.runtime import DeadlineExceededError
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

from base_page import BasePage

import utils


class Event(polymodel.PolyModel):
  """Base class for every events pushed by buildbot's StatusPush."""
  eventid = db.IntegerProperty(required=True, indexed=False)
  projectname = db.StringProperty(required=True)
  projectstarted = db.DateTimeProperty(required=True)
  created = db.DateTimeProperty(auto_now_add=True)


class Change(Event):
  """Buildbot detected a change"""
  comments = db.TextProperty()
  files = db.StringListProperty()
  # Buildbot's master change number in changes.pck
  number = db.IntegerProperty(required=True)
  revision = db.StringProperty(indexed=False)
  when = db.DateTimeProperty(required=True)
  who = db.StringProperty(indexed=False)
  revlink = db.StringProperty(indexed=False)


class Build(Event):
  """Buildbot completed a build"""
  buildername = db.StringProperty(required=True)
  buildnumber = db.IntegerProperty(required=True)
  finished = db.DateTimeProperty(indexed=False)
  reason = db.TextProperty()
  results = db.IntegerProperty(indexed=False)
  revision = db.StringProperty()
  slave = db.StringProperty(indexed=False)
  text = db.StringListProperty()


class BuildStep(Event):
  """Buildbot completed a build step"""
  buildername = db.StringProperty(required=True)
  buildnumber = db.IntegerProperty(required=True)
  finished = db.DateTimeProperty(indexed=False)
  # TODO(maruel): Require it ASAP
  stepnumber = db.IntegerProperty(required=False, indexed=False)
  stepname = db.StringProperty(required=True)
  text = db.StringListProperty()
  results = db.IntegerProperty(indexed=False)


def ModelToStr(obj):
  """Converts a model to a human readable string, for debugging"""
  assert isinstance(obj, db.Model)
  out = [obj.__class__.__name__]
  for k in obj.properties():
    if k.startswith('_'):
      continue
    out.append('  %s: %s' % (k, str(getattr(obj, k))))
  return '\n'.join(out)


def onChangeAdded(packet):
  change = packet['payload']['change']
  obj = Change.gql(
      'WHERE projectname = :1 AND projectstarted = :2 AND number = :3',
      packet['project'], packet['projectstarted'],
      change['number']).get()
  if obj:
    logging.info('Received duplicate %s/%s event for %s %s' %
                 (packet['event'], packet['eventid'], obj.__class__.__name__,
                  obj.number))
    return None
  return Change(
      eventid=packet['id'],
      projectname=packet['project'],
      projectstarted=packet['projectstarted'],
      comments=change['comments'],
      files=change['files'],
      number=change['number'],
      revision=change['revision'],
      # TODO(maruel): Timezones
      when=datetime.datetime.fromtimestamp(change['when']),
      who=change['who'],
      revlink=change['revlink'])


def onBuildFinished(packet):
  build = packet['payload']['build']
  obj = Build.gql(
      'WHERE projectname = :1 AND projectstarted = :2 '
      'AND buildername = :3 AND buildnumber = :4',
      packet['project'], packet['projectstarted'],
      build['builderName'], build['number']).get()
  if obj:
    logging.info('Received duplicate %s/%d event for %s %s' %
                 (packet['event'], packet['id'], obj.__class__.__name__,
                  obj.build_number))
    return None
  # properties is an array of 3 values, keep the first 2 in a dict.
  props = dict(((i[0], i[1]) for i in build['properties']))
  return Build(
      eventid=packet['id'],
      projectname=packet['project'],
      projectstarted=packet['projectstarted'],
      buildername=build['builderName'],
      buildnumber=build['number'],
      # TODO(maruel): Timezones
      finished=datetime.datetime.fromtimestamp(build['times'][1]),
      reason=build['reason'],
      results=build.get('results', 0),
      revision=props.get('got_revision', props.get('revision', None)),
      slave=build['slave'],
      text=build['text'])


def onStepFinished(packet):
  payload = packet['payload']
  step = payload['step']
  # properties is an array of 3 values, keep the first 2 in a dict.
  props = dict(((i[0], i[1]) for i in payload['properties']))
  obj = BuildStep.gql(
      'WHERE projectname = :1 AND projectstarted = :2 '
      'AND buildername = :3 AND buildnumber = :4 AND stepname = :5',
      packet['project'], packet['projectstarted'],
      props['buildername'], props['buildnumber'],
      step['name']).get()
  if obj:
    logging.info('Received duplicate %s/%d event for %s %s' %
                 (packet['event'], packet['id'], obj.__class__.__name__,
                  obj.buildnumber))
    return None
  return BuildStep(
      eventid=packet['id'],
      projectname=packet['project'],
      projectstarted=packet['projectstarted'],
      buildername=props['buildername'],
      buildnumber=props['buildnumber'],
      # TODO(maruel): Send step number
      #number=???
      stepname=step['name'],
      text=step['text'],
      results=step.get('results', (0,))[0])


SUPPORTED_EVENTS = {
    'changeAdded': onChangeAdded,
    'buildFinished': onBuildFinished,
    'stepFinished': onStepFinished,
}


class StatusReceiver(BasePage):
  """Buildbot's HttpStatusPush event receiver"""
  @utils.admin_only
  def post(self):
    self.response.headers['Content-Type'] = 'text/plain'
    try:
      # TODO(maruel): Safety check, pwd?
      packets = json.loads(self.request.POST['packets'])
      # A list of packets should have been submitted, store each event.
      objs = []
      for index in xrange(len(packets)):
        packet = packets[index]
        # To simplify getKwargs.
        packet['projectname'] = packet['project']
        # TODO(maruel): Timezones
        ts = time.strptime(packet['started'].split('.', 1)[0],
                           '%Y-%m-%d %H:%M:%S')
        packet['projectstarted'] = (
            datetime.datetime.fromtimestamp(time.mktime(ts)))
        packet['eventid'] = packet['id']
        if not 'payload' in packet:
          packet['payload'] = json.loads(packet['payload_json'])
        functor = SUPPORTED_EVENTS.get(packet['event'], None)
        if not functor:
          continue
        obj = functor(packet)
        if obj:
          objs.append(obj)
      # Save all the objects at once to reduce the number of rpc.
      db.put(objs)
    except CapabilityDisabledError:
      logging.info('CapabilityDisabledError: read-only datastore')
      self.response.out.write('CapabilityDisabledError: read-only datastore')
      self.error(500)
      return
    except DeadlineExceededError:
      logging.info('DeadlineExceededError')
      self.response.out.write('DeadlineExceededError')
      self.error(500)
      return
    taskqueue.add(url='/restricted/status-processor')
    self.response.out.write('Success')


class RecentEvents(BasePage):
  """Returns the most recent events.

  Mostly for testing"""
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    limit = int(self.request.GET.get('limit', 25))
    nb = 0
    for obj in Event.gql('ORDER BY created DESC LIMIT %d' % limit):
      self.response.out.write('%s\n\n' % ModelToStr(obj))
      nb += 1
    logging.debug('RecentEvents(limit=%d) got %d' % (limit, nb))


class StatusProcessor(BasePage):
  """TODO(maruel): Implement http://crbug.com/21801

  i.e. implement GateKeeper on appengine, close the tree when the buildbot
  master shuts down, etc."""

  @utils.work_queue_only
  def post(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Success')
