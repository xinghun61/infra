# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
from datetime import datetime
import functools
import hashlib
import json
import logging
import os

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import app_identity

from shared.config import HOST_ACLS

compressed_separators = (',', ':')

def cross_origin_json(handler):
  @functools.wraps(handler)
  def headered_json_handler(self, *args):
    self.response.headers.add_header("Access-Control-Allow-Origin", "*")
    result = handler(self, *args)
    if result is not None:
      self.response.headers.add_header('Content-Type', 'application/json')
      self.response.write(compressed_json_dumps(result))
  return headered_json_handler

def filter_dict(d, keys):
  return {key: d[key] for key in d if key in keys}


def get_host_permissions(kind):
  """Returns compiled regex of allowed user email or True if everyone is
  allowed."""
  assert kind in ('read', 'write')
  if os.environ.get('SERVER_SOFTWARE', '').startswith('Development'):
    host = 'Development'
  else:
    host = app_identity.get_default_version_hostname()
  return HOST_ACLS[host][kind]

def has_permission(kind):
  if users.is_current_user_admin():
    logging.info('user is admin')
    return True
  email_pattern = get_host_permissions(kind)
  if email_pattern == 'everyone':
    return True
  user = users.get_current_user()
  logging.info('user: %s %s', user, 'xx' if not user else user.email())
  return user and bool(email_pattern.match(user.email()))


def read_access(handler):
  """Decorator ensuring current user has read access to this host."""
  @functools.wraps(handler)
  def ensure(self, *args, **kwargs):
    if not has_permission('read'):
      self.redirect(users.create_login_url(self.request.url))
      return
    return handler(self, *args, **kwargs)
  return ensure


def get_friendly_hostname():
  host = app_identity.get_default_version_hostname()
  # For a typical host 'xyz-cq-status.appspot.com', return 'Xyz'.
  return host.split('-')[0].capitalize() if host else '(Development)'


def memcachize(cache_check):
  def decorator(f):
    def memcachized(**kwargs):
      key = '%s.%s(%s)' % (
        f.__module__,
        f.__name__,
        ', '.join('%s=%r' % i for i in sorted(kwargs.items())),
      )
      cache = memcache.get(key)
      if cache is not None and cache_check(cache['timestamp'], kwargs):
        logging.debug('Memcache hit: ' + key)
      else:
        cache = {
          'value': f(**kwargs),
          'timestamp': timestamp_now(),
        }
        try:
          memcache.set(key, cache)
        except ValueError as e:
          logging.warning('Error setting memcache for %s: %s' % (key, e))
      return cache['value']
    return memcachized
  return decorator

def password_sha1(password):
  return hashlib.sha1(password).hexdigest()

def timestamp_now():
  return to_unix_timestamp(datetime.utcnow())

def to_unix_timestamp(dt):
  return calendar.timegm(dt.timetuple()) + dt.microsecond / 1e6

def compressed_json_dumps(value):
  return json.dumps(value, separators=compressed_separators)


def is_gerrit_issue(issue):
  """Returns true, if the issue is likely legacy Gerrit issue.

  Doesn't do database requests and guesses based purely on issue.
  """
  # Gerrit CQ used to post urls for Gerrit users usign same code as Rietveld.
  # The only easy way to distinguish Rietveld from Gerrit issue, is that
  # all Gerrit instances used numbers (so far) < 1M, while Rietveld issues are
  # >10M. Since March 2016, CQ started sending extra codereview_hostname
  # metadata explicitely, so guessing isn't necessary, and we can safely support
  # Gerrit issues >1M.
  try:
    issue = int(issue)
    return 0 < issue and issue < 10**6
  except (ValueError, TypeError):
    return False


def guess_legacy_codereview_hostname(issue):
  if is_gerrit_issue(issue):
    return 'chromium-review.googlesource.com'
  return 'codereview.chromium.org'  # Default Rietveld review site.


def get_full_patchset_url(codereview_hostname, issue, patchset):
  if codereview_hostname.split('.')[0].split('-')[-1] == 'review':
    # This is Gerrit, which has host-review.googlesource.com.
    templ = 'https://%s/#/c/%s/%s'
  else:
    # Rietveld.
    templ = 'https://%s/%s/#ps%s'
  return templ % (codereview_hostname, issue, patchset)
