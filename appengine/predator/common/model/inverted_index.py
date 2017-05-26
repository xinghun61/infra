# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class _GroupRoot(ndb.Model):
  """Root entity of a group of inverted index.

  The root keeps track of the number of documents in a collection.
  And it is the parent of all inverted index.
  """
  # Number of documents in a collection.
  n_of_doc = ndb.IntegerProperty(indexed=False, default=0)


class InvertedIndex(ndb.Model):
  """Maps a keyword to the number of documents with the keyword.

  With the inverted index and its root, we can compute the IDF (inverse document
  frequency) of a keyword, one example formula is as below:

  idf = log(N/(1 + n))
  N: Total number of documents in collection.
  n: number of documents that have this keyword.

  By using idf, we can filter out some common terms, for example:
  'base/...' files.
  """
  # Number of documents that have this keyword.
  n_of_doc = ndb.IntegerProperty(indexed=False, default=0)

  @classmethod
  def _GetRootModel(cls):
    """Returns a root model of all inverted index."""
    root_model_name = '%sRoot' % cls.__name__

    class _RootModel(_GroupRoot):

      @classmethod
      def _get_kind(cls):
        return root_model_name

    return _RootModel

  @classmethod
  def _GetRootKey(cls):
    return ndb.Key(cls._GetRootModel(), 1)

  @classmethod
  def GetRoot(cls):
    root_key = cls._GetRootKey()
    return root_key.get() or cls._GetRootModel()(key=root_key)

  @classmethod
  def _CreateKey(cls, keyword):
    return ndb.Key(cls.__name__, keyword)

  @classmethod
  def Get(cls, keyword):
    return cls._CreateKey(keyword).get()

  @classmethod
  def Create(cls, keyword):
    return cls(key=cls._CreateKey(keyword))
