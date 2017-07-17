# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.appengine_testcase import AppengineTestCase
from common.model.inverted_index import InvertedIndex


class _MockInvertedIndex(InvertedIndex):
  pass


class InvertedIndexTest(AppengineTestCase):

  def testGetRootModel(self):
    root_model_class = _MockInvertedIndex._GetRootModel()
    self.assertEqual('_MockInvertedIndexRoot', root_model_class._get_kind())
    self.assertTrue(issubclass(root_model_class, ndb.Model))

  def testGetRoot(self):
    inverted_index = (_MockInvertedIndex.Get('keyword') or
                      _MockInvertedIndex.Create('keyword'))
    inverted_index.put()
    self.assertEqual(_MockInvertedIndex.Get('keyword').GetRoot().n_of_doc, 0)
