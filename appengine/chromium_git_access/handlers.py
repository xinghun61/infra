# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import webapp2

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from components import auth
from components import datastore_utils
from components import utils


class AccessCheckEntry(ndb.Model):
  """Information about some attempt to check write access to Chromium git repo.

  Submitted by clients from gclient hooks in chromium/src.
  """
  # Class name of a parent key (identifying a shard).
  SHARD_ENTITY_CLASS = 'AccessCheckEntryShard_v1'

  # How many letters of entity ID (hex) to use to identify a shard.
  SHARD_PREFIX_LEN = 2

  # Properties used to construct entity ID.
  FINGERPRINT_PROPERTIES = frozenset([
    'checker_version',
    'chrome_internal_netrc_email',
    'chromium_netrc_email',
    'gclient_deps',
    'gclient_managed',
    'gclient_url',
    'git_user_email',
    'git_user_name',
    'git_version',
    'is_git',
    'is_home_set',
    'is_using_netrc',
    'netrc_file_mode',
    'platform',
    'push_works',
    'username',
  ])

  # Properties settable via HTTP POST from client.
  EXTERNAL_PROPERTIES = frozenset(list(FINGERPRINT_PROPERTIES) + [
    'push_duration_ms',
    'push_log',
  ])

  # When the entry was submitted.
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  # Client version that submitted this entry.
  checker_version = ndb.IntegerProperty()

  # True if chromium git checkout is used, False if svn.
  is_git = ndb.BooleanProperty()
  # True if HOME env var is set.
  is_home_set = ndb.BooleanProperty()
  # True if ~/.netrc file exists.
  is_using_netrc = ndb.BooleanProperty()
  # netrc file access mode.
  netrc_file_mode = ndb.IntegerProperty()

  # Git version, as reported by git --version.
  git_version = ndb.StringProperty()
  # System platform, as reported by sys.platform.
  platform = ndb.StringProperty()
  # User name in the system, as returned by getpass.getuser().
  username = ndb.StringProperty()
  # git email as seen by chromium/src repo.
  git_user_email = ndb.StringProperty()
  # git user name as seen by chromium/src repo.
  git_user_name = ndb.StringProperty()

  # email in ~/.netrc entry for chromium host, or None if missing.
  chromium_netrc_email = ndb.StringProperty()
  # email in ~/.netrc entry for chrome-internal host, or None if missing.
  chrome_internal_netrc_email = ndb.StringProperty()

  # 'deps_file' property of 'src' gclient solution.
  gclient_deps = ndb.StringProperty()
  # 'managed' property of 'src' gclient solution.
  gclient_managed = ndb.BooleanProperty()
  # 'url' property of 'src' gclient solution.
  gclient_url = ndb.StringProperty()

  # True if push attempt was successful.
  push_works = ndb.BooleanProperty()
  # Log of the push operation.
  push_log = ndb.TextProperty()
  # How long push took (ms), successful or not.
  push_duration_ms = ndb.IntegerProperty()


# Typo safety measures.
assert AccessCheckEntry.EXTERNAL_PROPERTIES.issubset(
    AccessCheckEntry._properties)  # pylint: disable=W0212


def get_routes():
  return [
    webapp2.Route(r'/', MainHandler),
    webapp2.Route(r'/_ah/warmup', WarmupHandler),
    webapp2.Route(
        r'/git_access/api/v1/reports/access_check', AccessCheckHandler),
  ]


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Nothing to see here')


class WarmupHandler(webapp2.RequestHandler):
  def get(self):
    auth.warmup()
    self.response.write('ok')


class AccessCheckHandler(auth.ApiHandler):
  # We don't care about XSRF since there's no authentication for POST anyway.
  xsrf_token_enforce_on = ()

  @auth.public
  def post(self):
    body = self.parse_body()
    if not isinstance(body.get('access_check'), dict):
      self.abort_with_error(400, text='Missing access_check dict')
    access_check = body['access_check']

    # All EXTERNAL_PROPERTIES are required.
    if not AccessCheckEntry.EXTERNAL_PROPERTIES.issubset(access_check):
      self.abort_with_error(400, text='Incomplete access_check dict')

    # Read entity properties from the request body.
    entity = AccessCheckEntry()
    for key, value in body['access_check'].iteritems():
      if key in AccessCheckEntry.EXTERNAL_PROPERTIES:
        try:
          setattr(entity, key, value)
        except (datastore_errors.BadValueError, ValueError):
          self.abort_with_error(400, text='Key %s has invalid type' % key)
      else:
        logging.warning('Skipping unknown key %s', key)

    def to_utf8(x):
      if isinstance(x, unicode):
        return x.encode('utf-8')
      return str(x)

    # Use important parts of the entity to derive its key. It's a simple way
    # to avoid having duplicate entities in db in case client submits
    # same report multiple times.
    fingerprint = []
    for key in sorted(list(AccessCheckEntry.FINGERPRINT_PROPERTIES)):
      fingerprint.append(to_utf8(getattr(entity, key, None)))
    fingerprint = hashlib.sha1('\0'.join(fingerprint)).hexdigest()

    # Shard across 256 shards to avoid creating too many entity groups, queries
    # are faster that way. Entity key will be mostly meaningless.
    entity.key = ndb.Key(
        AccessCheckEntry,
        fingerprint,
        parent=datastore_utils.shard_key(
            fingerprint,
            AccessCheckEntry.SHARD_PREFIX_LEN,
            AccessCheckEntry.SHARD_ENTITY_CLASS))
    entity.put()

    # Report id back to client, so that logs can be correlated with this entry.
    self.send_response({'ok': True, 'report_id': fingerprint})

  @auth.require(auth.is_admin)
  def get(self):
    """Dumps all collected reports as JSON."""
    # TODO(vadimsh): Add filtering?
    def to_dict(e):
      d = e.to_dict()
      d['_id'] = e.key.id()
      return utils.to_json_encodable(d)
    self.send_response({
      'reports': [to_dict(e) for e in AccessCheckEntry.query()],
    })
