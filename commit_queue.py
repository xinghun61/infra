# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Commit queue status."""

import cgi
import logging
import re
import sys
import urllib2

import simplejson as json
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext.db import polymodel

from base_page import BasePage
import utils


class Owner(db.Model):
  """key == email address."""
  email = db.EmailProperty()

  @staticmethod
  def to_key(owner):
    return '<%s>' % owner


class PendingCommit(db.Model):
  """parent is Owner."""
  issue = db.IntegerProperty()
  patchset = db.IntegerProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  done = db.BooleanProperty(default=False)

  @staticmethod
  def to_key(issue, patchset, owner):
    return '<%d-%d-%s>' % (issue, patchset, owner)


class VerificationEvent(polymodel.PolyModel):
  """parent is PendingCommit."""
  message = db.StringProperty()
  # From commit-queue/verification/base.py
  result = db.IntegerProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  timestamp = db.DateTimeProperty(auto_now=True)

  @property
  def as_html(self):
    raise NotImplementedError()


class TryServerEvent(VerificationEvent):
  name = 'try server'
  url = db.StringProperty()
  builder = db.StringProperty()
  build = db.IntegerProperty()

  @property
  def as_html(self):
    url = cgi.escape(self.url)
    return '<a href="%s">%s</a>' % (url, url)


class PresubmitEvent(VerificationEvent):
  name = 'presubmit'
  output = db.TextProperty()
  duration = db.FloatProperty()
  result_code = db.IntegerProperty()
  timed_out = db.BooleanProperty()

  @property
  def as_html(self):
    return '<pre>%s</pre>' % cgi.escape(self.output)


def get_owner(owner):
  """Efficient querying of Owner with memcache."""
  # pylint: disable=E1101
  key = Owner.to_key(owner)
  obj = memcache.get(key, namespace='Owner')
  if not obj:
    obj = Owner.get_or_insert(key, email=owner)
    memcache.set(key, obj, time=60*60, namespace='Owner')
  return obj


def get_pending_commit(issue, patchset, owner):
  """Efficient querying of PendingCommit with memcache."""
  # pylint: disable=E1101
  owner_obj = get_owner(owner)
  key = PendingCommit.to_key(issue, patchset, owner)
  obj = memcache.get(key, namespace='PendingCommit')
  if not obj:
    obj = PendingCommit.get_or_insert(
        key, parent=owner_obj, issue=issue, patchset=patchset, owner=owner)
    memcache.set(key, obj, time=60*60, namespace='PendingCommit')
  return obj


class Summary(BasePage):
  def get(self, resource):  # pylint: disable=W0221
    query = VerificationEvent.all().order('-timestamp')
    limit = self.request.get('limit')
    if limit and limit.isdigit():
      limit = int(limit)
    else:
      limit = 100

    resource = resource.strip('/')
    resource = urllib2.unquote(resource)
    if resource:
      if resource == 'me':
        resource = self.user.email()
      if resource:
        logging.debug('Filtering on %s' % resource)
        query.ancestor(db.Key.from_path("Owner", Owner.to_key(resource)))

    out_format = self.request.get('format', 'html')
    if out_format == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.headers['Access-Control-Allow-Origin'] = '*'
      data = json.dumps([s.AsDict() for s in query.fetch(limit)])
      callback = self.request.get('callback')
      if callback:
        if re.match(r'^[a-zA-Z$_][a-zA-Z$0-9._]*$', callback):
          data = '%s(%s);' % (callback, data)
      self.response.out.write(data)
    else:
      template_values = self.InitializeTemplate(self.app_name + ' Commit queue')
      template_values['events'] = query.fetch(limit)
      self.DisplayTemplate('cq_summary.html', template_values, use_cache=True)


class Receiver(BasePage):
  # Verification name in commit-queue/verification/*.py
  _EVENT_MAP = None

  @staticmethod
  def event_map():
    # Used by _parse_packet() to find the right model to use from the
    # 'verification' value of the packet.
    if Receiver._EVENT_MAP is None:
      Receiver._EVENT_MAP = {}
      module = sys.modules[__name__]
      for i in dir(module):
        if i.endswith('Event') and i != 'VerificationEvent':
          obj = getattr(module, i)
          Receiver._EVENT_MAP[obj.name] = obj
    return Receiver._EVENT_MAP

  @utils.admin_only
  def post(self):
    def load_values():
      for p in self.request.get_all('p'):
        try:
          yield json.loads(p)
        except ValueError:
          logging.warn('Discarding invalid packet %r' % p)
    packets = list(self._parse_packet(p for p in load_values()))
    db.put(packets)
    self.response.out.write('%d\n' % len(packets))

  @staticmethod
  def _parse_packet(packets):
    for packet in packets:
      cls = Receiver.event_map().get(packet.get('verification'))
      if (not cls or
          not isinstance(packet.get('issue'), int) or
          not isinstance(packet.get('patchset'), int) or
          not packet.get('timestamp') or
          not isinstance(packet.get('owner'), basestring)):
        logging.warning('Ignoring packet %s' % packet)
        continue
      payload = packet.get('payload', {})
      values = dict(
          (i, payload.get(i)) for i in cls.properties() if not i == 'pending')
      pending = get_pending_commit(
          packet['issue'], packet['patchset'], packet['owner'])
      logging.debug('New packet %s' % cls.__name__)
      yield cls(parent=pending, **values)
