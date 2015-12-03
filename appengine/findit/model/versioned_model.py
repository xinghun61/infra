# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides a model to support versioned entities in datastore.

Idea: use a root model entity to keep track of the most recent version of a
versioned entity, and make the versioned entities and the root model entity in
the same entity group so that they could be read and written in a transaction.
"""

import logging

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb
from google.appengine.runtime import apiproxy_errors


class _GroupRoot(ndb.Model):
  """Root entity of a group to support versioned children."""
  # Key id of the most recent child entity in the datastore. It is monotonically
  # increasing and is 0 if no child is present.
  current = ndb.IntegerProperty(indexed=False, default=0)


class VersionedModel(ndb.Model):
  """A model that supports versioning.

  Subclass will automatically be versioned, if use GetMostRecentVersion() to
  read and use Save() to write.
  """

  @property
  def version(self):
    return self.key.integer_id()

  @classmethod
  def GetMostRecentVersion(cls):
    """Returns the most recent version of the entity."""
    assert not ndb.in_transaction()

    root_key = cls._GetRootKey()
    root = root_key.get()
    if not root or not root.current:
      return None

    return ndb.Key(cls, root.current, parent=root_key).get()

  def Save(self):
    """Saves the current entity, but as a new version."""
    root_key = self._GetRootKey()
    root = root_key.get() or self._GetRootModel()(key=root_key)

    def SaveData():
      if self.key.get():
        return False  # The entity exists, should retry.
      ndb.put_multi([self, root])
      return True

    def SetNewKey():
      root.current += 1
      self.key = ndb.Key(self.__class__, root.current, parent=root_key)

    SetNewKey()
    while True:
      while self.key.get():
        SetNewKey()

      try:
        if ndb.transaction(SaveData, retries=0):
          return self.key
      except (
          datastore_errors.InternalError,
          datastore_errors.Timeout,
          datastore_errors.TransactionFailedError) as e:
        # https://cloud.google.com/appengine/docs/python/datastore/transactions
        # states the result is ambiguous, it could have succeeded.
        logging.info('Transaction likely failed: %s', e)
      except (
          apiproxy_errors.CancelledError,
          datastore_errors.BadRequestError,
          RuntimeError) as e:
        logging.info('Transaction failure: %s', e)
      else:
        SetNewKey()

  @classmethod
  def _GetRootModel(cls):
    """Returns a root model that can be used for versioned entities."""
    root_model_name = '%sRoot' % cls.__name__

    class _RootModel(_GroupRoot):
      @classmethod
      def _get_kind(cls):
        return root_model_name

    return _RootModel

  @classmethod
  def _GetRootKey(cls):
    return ndb.Key(cls._GetRootModel(), 1)
