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

  Subclasses will automatically be versioned. To create the first instance of a
  versioned entity, use Create(key) with optional key to differentiate between
  multiple unique entities of the same subclass. Use GetVersion() to read and
  Save() to write.
  """

  @property
  def _root_id(self):
    return self.key.pairs()[0][1] if self.key else None

  @property
  def version_number(self):
    # Ndb treats key.integer_id() of 0 as None, so default to 0.
    return self.key.integer_id() or 0 if self.key else 0

  @classmethod
  def Create(cls, key=None):
    """Creates an instance of cls that is to become the first version.

    The calling function of Create() should be responsible first for checking
    no previous version of the proposed entity already exists.

    Args:
      key: Any user-specified value that will serve as the id for the root
        entity's key.

    Returns:
      An instance of cls meant to be the first version. Note for this instance
        to be committed to the datastore Save() would need to be called on the
        instance returned by this method.
    """
    return cls(key=ndb.Key(cls, 0, parent=cls._GetRootKey(key)))

  @classmethod
  def GetVersion(cls, key=None, version=None):
    """Returns a version of the entity, the latest if version=None."""
    assert not ndb.in_transaction()

    root_key = cls._GetRootKey(key)
    root = root_key.get()

    if not root or not root.current:
      return None

    if version is None:
      version = root.current
    elif version < 1:
      #  Return None for versions < 1, which causes exceptions in ndb.Key()
      return None

    return ndb.Key(cls, version, parent=root_key).get()

  @classmethod
  def GetLatestVersionNumber(cls, key=None):
    root_entity = cls._GetRootKey(key).get()
    if not root_entity:
      return -1
    return root_entity.current

  def Save(self, retry_on_conflict=True):
    """Saves the current entity, but as a new version.

    Args:
      retry_on_conflict (bool): Whether or not the next version number should
        automatically be tried in case another transaction writes the entity
        first with the same proposed new version number.

    Returns:
      The key of the newly written version, and a boolean whether or not this
      call to Save() was responsible for creating it.
    """
    root_key = self._GetRootKey(self._root_id)
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
        if retry_on_conflict:
          SetNewKey()
        else:
          # Another transaction had already written the proposed new version, so
          # return that version's key and False indicating this call to Save()
          # was not responsible for creating it.
          return self.key, False

      try:
        if ndb.transaction(SaveData, retries=0):
          return self.key, True
      except (datastore_errors.InternalError, datastore_errors.Timeout,
              datastore_errors.TransactionFailedError) as e:
        # https://cloud.google.com/appengine/docs/python/datastore/transactions
        # states the result is ambiguous, it could have succeeded.
        logging.info('Transaction likely failed: %s', e)
      except (apiproxy_errors.CancelledError, datastore_errors.BadRequestError,
              RuntimeError) as e:
        logging.info('Transaction failure: %s', e)
      else:
        if retry_on_conflict:
          SetNewKey()
        else:
          # Another transaction had already written the proposed new version, so
          # return that version's key and False indicating this call to Save()
          # was not responsible for creating it.
          return self.key, False

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
  def _GetRootKey(cls, key=None):
    return ndb.Key(cls._GetRootModel(), key if key is not None else 1)
