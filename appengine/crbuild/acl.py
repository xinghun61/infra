# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(nodir): write tests for ACL

from components import auth
from google.appengine.api import users
import endpoints



HOSTNAME_WHITELIST = {
    'quickoffice-internal-review.googlesource.com',
    'chromium-review.googlesource.com',
    'chrome-internal-review.googlesource.com',
}


def hostname_is_allowed(hostname):  # pragma: no cover
  # At some point, we may change this to hostname.endswith('.googlesource.com')
  return hostname in HOSTNAME_WHITELIST


def current_user():  # pragma: no cover
  return CrbuildUser(auth.get_current_identity())


# pylint: disable=W0613
class CrbuildUser(object):  # pragma: no cover
  def __init__(self, identity):
    self.identity = identity

  @property
  def is_admin(self):
    return auth.is_admin(self.identity)

  @property
  def name(self):
    return self.identity.name

  def can_add_build_to_namespace(self, namespace):
    return self.is_admin

  def can_peek_namespace(self, tag):
    return self.is_admin

  def can_lease_build(self, build):
    return self.is_admin

  def can_cancel_build(self, build):
    return self.is_admin

  def can_view_cl(self, cl):
    return self.is_admin

  def can_view_build(self, build):
    return self.is_admin

  def __str__(self):
    return str(self.name)
