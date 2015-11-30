# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Findit for Waterfall configuration."""

from google.appengine.ext import ndb

from components import datastore_utils
from components.datastore_utils import config


class FinditConfig(config.GlobalConfig):
  """Singleton entity with the global configuration of findit."""
  # A Dict mapping supported masters to lists of unsupported steps.
  masters_to_blacklisted_steps = ndb.JsonProperty(indexed=False, default={})

  # Mapping of waterfall builders to try-server trybots, which are used to
  # re-run compile to identify culprits for compile failures.
  builders_to_trybots = ndb.JsonProperty(indexed=False, default={})

  @property
  def VersionNumber(self):  # pragma: no cover
    return datastore_utils.HIGH_KEY_ID - self.key.integer_id()


def Settings(fresh=False):  # pragma: no cover
  if fresh:
    FinditConfig.clear_cache()
  return FinditConfig.cached()


def Update(new_config_dict):  # pragma: no cover
  conf = Settings()
  conf.modify(**new_config_dict)
