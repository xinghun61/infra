# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Commit queue status."""

import cgi
import datetime
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


TRY_SERVER_MAP = [
    'SUCCESS', 'WARNINGS', 'FAILURE', 'SKIPPED', 'EXCEPTION', 'RETRY',
]


class Owner(db.Model):
  """key == email address."""
  email = db.EmailProperty()

  @staticmethod
  def to_key(owner):
    return '<%s>' % owner


class PendingCommit(db.Model):
  """parent is Owner."""
  created = db.DateTimeProperty()
  done = db.BooleanProperty(default=False)
  issue = db.IntegerProperty()
  patchset = db.IntegerProperty()

  @staticmethod
  def to_key(issue, patchset, owner):
    return '<%d-%d-%s>' % (issue, patchset, owner)


class VerificationEvent(polymodel.PolyModel):
  """parent is PendingCommit."""
  created = db.DateTimeProperty(auto_now_add=True)
  result = db.IntegerProperty()
  timestamp = db.DateTimeProperty()

  @property
  def as_html(self):
    raise NotImplementedError()

  @staticmethod
  def to_key(packet):
    raise NotImplementedError()


class TryServerEvent(VerificationEvent):
  name = 'try server'
  build = db.IntegerProperty()
  builder = db.StringProperty()
  clobber = db.BooleanProperty()
  job_name = db.StringProperty()
  revision = db.IntegerProperty()
  url = db.StringProperty()

  @property
  def as_html(self):
    if self.build is not None:
      out = '<a href="%s">"%s" on %s, build #%s</a>' % (
          cgi.escape(self.url),
          cgi.escape(self.job_name),
          cgi.escape(self.builder),
          cgi.escape(str(self.build)))
      if (self.result is not None and
          0 <= self.result < len(TRY_SERVER_MAP[self.result])):
        out = '%s - result: %s' % (out, TRY_SERVER_MAP[self.result])
      return out
    else:
      # TODO(maruel): Load the json
      # ('http://build.chromium.org/p/tryserver.chromium/json/builders/%s/'
      #  'pendingBuilds') % self.builder and display the rank.
      return '"%s" on %s (pending)' % (
          cgi.escape(self.job_name),
          cgi.escape(self.builder))

  @staticmethod
  def to_key(packet):
    if not packet.get('builder') or not packet.get('job_name'):
      return None
    return '<%s-%s-%s>' % (
        TryServerEvent.name, packet['builder'], packet['job_name'])


class PresubmitEvent(VerificationEvent):
  name = 'presubmit'
  duration = db.FloatProperty()
  output = db.TextProperty()
  timed_out = db.BooleanProperty()

  @property
  def as_html(self):
    return '<pre class="output">%s</pre>' % cgi.escape(self.output)

  @staticmethod
  def to_key(_):
    # There shall be only one PresubmitEvent per PendingCommit.
    return '<%s>' % (PresubmitEvent.name)


class CommitEvent(VerificationEvent):
  name = 'commit'
  output = db.TextProperty()
  revision = db.IntegerProperty()
  url = db.StringProperty()

  @property
  def as_html(self):
    out = '<pre class="output">%s</pre>' % cgi.escape(self.output)
    if self.url:
      out += '<a href="%s">Revision %s</a>' % (
        cgi.escape(self.url),
        cgi.escape(str(self.revision)))
    elif self.revision:
      out += '<br>Revision %s' % cgi.escape(str(self.revision))
    return out

  @staticmethod
  def to_key(_):
    return '<%s>' % (CommitEvent.name)


def get_owner(owner):
  """Efficient querying of Owner with memcache."""
  # pylint: disable=E1101
  key = Owner.to_key(owner)
  obj = memcache.get(key, namespace='Owner')
  if not obj:
    obj = Owner.get_or_insert(key_name=key, email=owner)
    memcache.set(key, obj, time=60*60, namespace='Owner')
  return obj


def get_pending_commit(issue, patchset, owner, timestamp):
  """Efficient querying of PendingCommit with memcache."""
  # pylint: disable=E1101
  owner_obj = get_owner(owner)
  key = PendingCommit.to_key(issue, patchset, owner)
  obj = memcache.get(key, namespace='PendingCommit')
  if not obj:
    obj = PendingCommit.get_or_insert(
        key_name=key, parent=owner_obj, issue=issue, patchset=patchset,
        owner=owner, created=timestamp)
    memcache.set(key, obj, time=60*60, namespace='PendingCommit')
  return obj


class Summary(BasePage):
  def get(self, resource):  # pylint: disable=W0221
    out_format = self.request.get('format', 'html')
    resource = resource.strip('/')
    resource = urllib2.unquote(resource)
    if resource:
      if resource == 'me':
        resource = self.user.email()
    if out_format == 'json':
      return self.get_json(resource)
    else:
      return self.get_html(resource)

  def get_json(self, owner):
    query = VerificationEvent.all().order('-timestamp')
    limit = self.request.get('limit')
    if limit and limit.isdigit():
      limit = int(limit)
    else:
      limit = 100
    if owner:
      query.ancestor(db.Key.from_path("Owner", Owner.to_key(owner)))

    self.response.headers['Content-Type'] = 'application/json'
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    data = json.dumps([s.AsDict() for s in query.fetch(limit)])
    callback = self.request.get('callback')
    if callback:
      if re.match(r'^[a-zA-Z$_][a-zA-Z$0-9._]*$', callback):
        data = '%s(%s);' % (callback, data)
    self.response.out.write(data)

  def get_html(self, owner):
    # HTML version.
    if not owner:
      return self.get_html_owners()
    else:
      return self.get_html_owner(owner)

  def get_html_owners(self):
    owners = []
    # No need to sort.
    for owner in Owner.all():
      # Revisit when it becomes too costly to display.
      q = lambda: PendingCommit.all().ancestor(owner)
      now = datetime.datetime.utcnow()
      t = lambda x: now - datetime.timedelta(days=x)
      data = {
          'last_day':
              ', '.join(str(i.issue) for i in q().filter('created >=', t(1))),
          'last_week':
              ', '.join(
                str(i.issue) for i in q().filter('created >=',  t(7)
                  ).filter('created <', t(1))),
          'last_month': q().filter('created >=', t(30)).count(),
          'forever': q().count(),
        }
      owners.append((owner.email, data))
    template_values = self.InitializeTemplate(self.app_name + ' Commit queue')
    template_values['data'] = owners
    self.DisplayTemplate('cq_owners.html', template_values, use_cache=True)

  def get_html_owner(self, owner):
    query = VerificationEvent.all().order('-timestamp')
    limit = self.request.get('limit')
    if limit and limit.isdigit():
      limit = int(limit)
    else:
      limit = 100
    query.ancestor(db.Key.from_path("Owner", Owner.to_key(owner)))
    pending_commits_events = {}
    pending_commits = {}
    for event in query.fetch(limit):
      # Implicitly find PendingCommit's.
      pending_commit = event.parent()
      if not pending_commit:
        logging.warn('Event %s is corrupted, can\'t find %s' % (
          event.key().id_or_name(), event.parent_key().id_or_name()))
        continue
      pending_commits_events.setdefault(pending_commit.key(), []).append(event)
      pending_commits[pending_commit.key()] = pending_commit

    sorted_data = []
    for pending_commit in sorted(
        pending_commits.itervalues(), key=lambda x: x.issue):
      sorted_data.append(
          (pending_commit,
            reversed(pending_commits_events[pending_commit.key()])))
    template_values = self.InitializeTemplate(self.app_name + ' Commit queue')
    template_values['data'] = sorted_data
    self.DisplayTemplate('cq_owner.html', template_values, use_cache=True)


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

    count = 0
    for packet in load_values():
      cls = self.event_map().get(packet.get('verification'))
      if (not cls or
          not isinstance(packet.get('issue'), int) or
          not isinstance(packet.get('patchset'), int) or
          not packet.get('timestamp') or
          not isinstance(packet.get('owner'), basestring)):
        logging.warning('Ignoring packet %s' % packet)
        continue

      payload = packet.get('payload', {})
      # TODO(maruel): Convert the type implicitly, because storing a int into a
      # FloatProperty or a StringProperty will raise a BadValueError.
      values = dict(
          (i, payload[i]) for i in cls.properties()
          if i not in ('_class', 'pending') and i in payload)
      # Inject the timestamp.
      values['timestamp'] = datetime.datetime.utcfromtimestamp(
          packet['timestamp'])
      pending = get_pending_commit(
          packet['issue'], packet['patchset'], packet['owner'],
          values['timestamp'])

      logging.debug('New packet %s' % cls.__name__)
      key_name = cls.to_key(values)
      if not key_name:
        continue

      # TODO(maruel) Use an async transaction, in batch.
      obj = cls.get_by_key_name(key_name, parent=pending)
      # Compare the timestamps. Events could arrive in the reverse order.
      if not obj or obj.timestamp <= values['timestamp']:
        # This will override the previous obj if it existed.
        cls(parent=pending, key_name=key_name, **values).put()
        count += 1
      elif obj:
        logging.warn('Received object out of order')

      # Cache the fact that the change was committed in the PendingCommit.
      if packet['verification'] == 'commit':
        pending.done = True
        pending.put()

    self.response.out.write('%d\n' % count)
