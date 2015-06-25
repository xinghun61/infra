# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os

from google.appengine.ext import ndb

CONFIG_DATA_KEY = 'config_data_key'
TRAFFIC_SPLIT_KEY = 'traffic_split_key'
# Header name to pass the endpoint URL to the backend.
# Note the capitalization: HTTP headers are enforced to have this pattern.
ENDPOINT_URL_HEADER = 'Endpoint-Url'


class Credentials(ndb.Model):
  """Store a service account credentials."""
  client_email   = ndb.StringProperty(required=True, default='')
  private_key    = ndb.StringProperty(required=True, default='')
  private_key_id = ndb.StringProperty(required=True, default='')
  client_id      = ndb.StringProperty(default='')


class Endpoint(ndb.Model):
  url = ndb.StringProperty(required=True)
  credentials = ndb.StructuredProperty(Credentials, default=Credentials())
  scopes = ndb.StringProperty(repeated=True)
  headers = ndb.JsonProperty(default={})


class ConfigData(ndb.Model):
  primary_endpoint = ndb.StructuredProperty(Endpoint, default=Endpoint())
  secondary_endpoint = ndb.StructuredProperty(Endpoint, default=Endpoint())
  secondary_endpoint_load = ndb.IntegerProperty(default=0)


class TrafficSplit(ndb.Model):
  """Store load percentage [0..100] for each VM module.

  Used to drain / ramp up the modules for rolling updates in production.
  """
  vm1 = ndb.IntegerProperty(default=100)
  vm2 = ndb.IntegerProperty(default=100)
  vm3 = ndb.IntegerProperty(default=100)


def payload_stats(data):
  md5 = hashlib.md5()
  md5.update(data)
  md5hex = md5.hexdigest()
  return 'type=%s, %d bytes, md5=%s' % (type(data), len(data), md5hex)
