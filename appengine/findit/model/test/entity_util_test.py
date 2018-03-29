# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.testcase import TestCase
from model import entity_util


class TestModel(ndb.Model):
  """Ndb model to assist unit tests for this class."""
  name = ndb.StringProperty()


class ModelUtilTest(TestCase):

  def testGetEntityFromUrlsafeKey(self):
    self.assertEqual(None, entity_util.GetEntityFromUrlsafeKey(None))
    self.assertEqual(None, entity_util.GetEntityFromUrlsafeKey('notvalid'))

    model = TestModel(name='name')
    model.put()
    k = model.key.urlsafe()
    self.assertEqual(model, entity_util.GetEntityFromUrlsafeKey(k))
