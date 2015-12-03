# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Versioned singleton entity with the global configuration."""

import logging

from google.appengine.api import users
from google.appengine.ext import ndb

from model.versioned_model import VersionedModel


class VersionedConfig(VersionedModel):
  """Singleton entity with the global configuration of the service.

  All changes are stored in the revision log.
  """

  # When this revision of configuration was created.
  updated_ts = ndb.DateTimeProperty(indexed=False, auto_now_add=True)

  # Who created this revision of configuration.
  updated_by = ndb.StringProperty(indexed=False)

  @classmethod
  def Get(cls):
    """Returns the current up-to-date version of the config entity."""
    return cls.GetMostRecentVersion() or cls()

  def Update(self, **kwargs):
    """Applies |kwargs| dict to the entity and stores the entity if changed."""
    if not users.is_current_user_admin():
      raise Exception('Only admin could update config.')

    dirty = False
    for k, v in kwargs.iteritems():
      assert k in self._properties, k
      if getattr(self, k) != v:
        setattr(self, k, v)
        dirty = True

    if dirty:
      user_name = users.get_current_user().email().split('@')[0]
      self.updated_by = user_name
      self.Save()
      logging.info('Config %s was updated by %s', self.__class__, user_name)

    return dirty
