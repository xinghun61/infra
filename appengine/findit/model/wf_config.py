# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Findit for Waterfall configuration."""

from google.appengine.ext import ndb

from model.versioned_config import VersionedConfig


class FinditConfig(VersionedConfig):
  """Global configuration of findit."""
  # A Dict mapping supported masters to lists of unsupported steps.
  masters_to_blacklisted_steps = ndb.JsonProperty(indexed=False, default={})

  # Mapping of waterfall builders to try-server trybots, which are used to
  # re-run compile to identify culprits for compile failures.
  builders_to_trybots = ndb.JsonProperty(indexed=False, default={})
