# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Global application configuration."""

from google.appengine.ext import ndb

from components import config


class GlobalConfig(config.GlobalConfig):
  """Singleton entity with the global configuration of the service."""
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


def cached():  # pragma: no cover
  """Returns memory cached GlobalConfig object with global configuration."""
  return GlobalConfig.cached()
