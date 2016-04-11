# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import hashlib
import json
import logging
from urlparse import urlparse
import webapp2

from components import auth
from components import decorators
from google.appengine.ext import ndb
from google.appengine.ext import db

import utils


def bug_validator(_, value):
  try:
    return "https://crbug.com/%d" % int(value)
  except ValueError:
    pass

  parsed = urlparse(value)
  for allowed in ('bugs.chromium.org', 'crbug.com'):
    if allowed in parsed.netloc:
      return None

  raise db.BadValueError("Invalid bug %s" % value)


class Annotation(ndb.Model):
  """Annotation for an alert in SoM.

  Datastore key is the SHA1 digest of the alert key, since some alerts can be
  larger than 500 bytes, which is an appengine size limit for key size.
  """
  alert_key = ndb.TextProperty()
  bugs = ndb.StringProperty(
      repeated=True, indexed=False, validator=bug_validator)
  snooze_time = ndb.IntegerProperty()
  modification_time = ndb.DateTimeProperty(auto_now_add=True)

  @staticmethod
  def annotation_key(alert_key):
    digest = utils.hash_string(alert_key)
    return ndb.Key(Annotation, digest)

  def update(self, change):
    if 'remove' in change:
      remove = change['remove']
      if remove.get('snoozeTime'):
        self.snooze_time = None
      if remove.get('bugs'):
        self.bugs = list(
            set(self.bugs) - set(
                bug_validator(self, bug) or bug for bug in remove.get('bugs')))

    if 'add' in change:
      add = change['add']
      if add.get('snoozeTime'):
        self.snooze_time = add['snoozeTime']
      if add.get('bugs'):
        self.bugs = set(list(self.bugs + add.get('bugs')))

    self.bugs = sorted(set(self.bugs))

  def serialize(self):
    return {
      'snoozeTime': self.snooze_time,
      'key': self.alert_key,
      'bugs': self.bugs,
    }

class AnnotationsListHandler(auth.AuthenticatingHandler):
  @auth.public
  def get(self):
    results = []

    for annotation in Annotation.query():
      results.append(annotation.serialize())

    self.response.headers['Content-Type'] = 'application/json'
    self.response.write(json.dumps(results))

class AnnotationHandler(auth.AuthenticatingHandler):
  xsrf_token_enforce_on = []
  xsrf_token_request_param = None

  @auth.require(utils.is_googler)
  def post(self, annotation_key):
    key = Annotation.annotation_key(annotation_key)
    annotation = key.get()
    if not annotation:
      annotation = Annotation(key=key, alert_key=annotation_key)

    # TODO(martiniss): make this a transaction, since multiple changes can
    # conflict
    changes = json.loads(self.request.body)
    for change in changes:
      try:
        annotation.update(change)
        annotation.put()
      except db.BadValueError as e:
        self.response.write(e)
        self.response.set_status(400)
        return

    self.response.headers['Content-Type'] = 'application/json'
    self.response.write(json.dumps(annotation.serialize()))


ANNOTATION_EXPIRATION_TIME = datetime.timedelta(days=7)


def _cleanup_old_annotations():
  annotations = Annotation.query().filter(
      Annotation.modification_time < (
          datetime.datetime.now() - ANNOTATION_EXPIRATION_TIME)).fetch()

  if not annotations:
    logging.debug("No annotations to delete. Exiting...")
    return

  for annotation in annotations:
    logging.debug("deleting %s" % annotation.alert_key)
    annotation.key.delete()


class AnnotationCleanupHandler(webapp2.RequestHandler):
  @decorators.require_cronjob
  def get(self):
    _cleanup_old_annotations()

app = webapp2.WSGIApplication([
    ('/api/v1/annotations', AnnotationsListHandler),
    ('/api/v1/annotations/(.*)', AnnotationHandler),
    ('/internal/cron/cleanup_old_annotations', AnnotationCleanupHandler),
])
