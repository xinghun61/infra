# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Global application configuration."""

from google.appengine.ext import ndb

from components import auth
from components import datastore_utils
from components import utils


class GlobalConfig(ndb.Model):
  """Singleton entity with the global configuration of the service.

  All changes are stored in the revision log.
  """
  # Used by datastore_utils.store_new_version.
  ROOT_MODEL = datastore_utils.get_versioned_root_model('GlobalConfigRoot')
  ROOT_KEY = ndb.Key(ROOT_MODEL, 1)

  # When this revision of configuration was created.
  updated_ts = ndb.DateTimeProperty(indexed=False, auto_now_add=True)
  # Who created this revision of configuration.
  updated_by = auth.IdentityProperty(indexed=False)

  # GS path to store verified objects in as <cas_gs_path>/SHA1/<hexdigest>.
  cas_gs_path = ndb.StringProperty(indexed=False)
  # GS path to store temporary uploads in (may be in another bucket).
  cas_gs_temp = ndb.StringProperty(indexed=False)

  # Service account email to use to sign Google Storage URLs.
  service_account_email = ndb.StringProperty(indexed=False)
  # Service account private key, as PEM-encoded *.der.
  service_account_pkey = ndb.TextProperty(indexed=False)
  # Service account private key fingerprint.
  service_account_pkey_id = ndb.StringProperty(indexed=False)

  @classmethod
  def fetch(cls):
    """Returns the current version of the instance."""
    return datastore_utils.get_versioned_most_recent(cls, cls.ROOT_KEY)

  def store(self, updated_by=None):
    """Stores a new version of the instance."""
    # Create an incomplete key, to be completed by 'store_new_version'.
    self.key = ndb.Key(self.__class__, None, parent=self.ROOT_KEY)
    self.updated_by = updated_by or auth.get_current_identity()
    return datastore_utils.store_new_version(self, self.ROOT_MODEL)

  def modify(self, updated_by=None, **kwargs):
    """Applies |kwargs| dict to the entity and stores it if it changed."""
    dirty = False
    for k, v in kwargs.iteritems():
      assert k in self._properties, k
      if getattr(self, k) != v:
        setattr(self, k, v)
        dirty = True
    if dirty:
      self.store(updated_by=updated_by)
    return dirty


@utils.cache_with_expiration(expiration_sec=60)
def config():
  """Returns GlobalConfig object with global configuration."""
  conf = GlobalConfig.fetch()
  if not conf:
    conf = GlobalConfig()
    conf.store(updated_by=auth.get_service_self_identity())

  # Allow customization hook on dev server for adhoc testing. For example,
  # local_dev_config may switch 'cloudstorage' library to talk to real GCS.
  if utils.is_local_dev_server():  # pragma: no cover
    try:
      import local_dev_config
      local_dev_config.apply(conf)
    except ImportError:
      pass

  return conf


def warmup():
  """Called from /_ah/warmup handler."""
  config()
