# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities that are useful for any kind of ndb entity."""

import logging

from google.appengine.ext import ndb


def GetEntityFromUrlsafeKey(urlsafe_key):
  """Retrieves a model from a given urlsafe key or None if exception occurs."""
  try:
    entity = ndb.Key(urlsafe=urlsafe_key).get()
  # Actually ProtocolBufferDecodeError, which is missing from libs.
  except:  # pylint: disable=bare-except
    logging.exception('Coudn\'t get ndb key from given urlsafe key %s',
                      urlsafe_key)
    entity = None

  return entity
