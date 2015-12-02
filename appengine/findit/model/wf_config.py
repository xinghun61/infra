# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Findit for Waterfall configuration."""

from google.appengine.ext import ndb

from components import datastore_utils


# TODO(lijeffrey): It seems importing config from luci causes import breakages
# in other parts of the code. Need to debug and fix the import error and
# subclass FinditConfig from config.GlobalConfig if possible.
class FinditConfig(ndb.Model):
  """Singleton entity with the global configuration of findit."""
  _config_fetcher = None

  # A Dict mapping supported masters to lists of unsupported steps.
  masters_to_blacklisted_steps = ndb.JsonProperty(indexed=False, default={})

  # Mapping of waterfall builders to try-server trybots, which are used to
  # re-run compile to identify culprits for compile failures.
  builders_to_trybots = ndb.JsonProperty(indexed=False, default={})

  @property
  def VersionNumber(self):  # pragma: no cover
    return datastore_utils.HIGH_KEY_ID - self.key.integer_id()

  @classmethod
  def _get_root_model(cls):  # pragma: no cover
    return datastore_utils.get_versioned_root_model('%sRoot' % cls.__name__)

  @classmethod
  def _get_root_key(cls):  # pragma: no cover
    return ndb.Key(cls._get_root_model(), 1)

  @classmethod
  def fetch(cls):  # pragma: no cover
    """Returns the current up-to-date version of the config entity.

    Always fetches it from datastore. May return None if missing.
    """
    return datastore_utils.get_versioned_most_recent(cls, cls._get_root_key())

  @classmethod
  def cached(cls):  # pragma: no cover
    if not cls._config_fetcher:
      def config_fetcher():
        conf = cls.fetch()
        if not conf:
          conf = cls()
          conf.store()
        return conf
      cls._config_fetcher = staticmethod(config_fetcher)
    return cls._config_fetcher()

  def store(self):  # pragma: no cover
    """Stores a new version of the config entity."""
    # Create an incomplete key, to be completed by 'store_new_version'.
    self.key = ndb.Key(self.__class__, None, parent=self._get_root_key())
    return datastore_utils.store_new_version(self, self._get_root_model())

  def modify(self, **kwargs):  # pragma: no cover
    """Applies |kwargs| dict to the entity and stores the entity if changed."""
    dirty = False
    for k, v in kwargs.iteritems():
      assert k in self._properties, k
      if getattr(self, k) != v:
        setattr(self, k, v)
        dirty = True
    if dirty:
      self.store()
    return dirty

  # Mapping of waterfall builders to try-server trybots, which are used to
  # re-run compile to identify culprits for compile failures.
  builders_to_trybots = ndb.JsonProperty(indexed=False, default={})


def Settings():  # pragma: no cover
  return FinditConfig.cached()


def Update(new_config_dict):  # pragma: no cover
  conf = Settings()
  conf.modify(**new_config_dict)
