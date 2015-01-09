# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel


class _DummyModel(BaseBuildModel):
  @staticmethod
  def Create(master_name, builder_name, build_number):
    key = ndb.Key('M', BaseBuildModel.CreateBuildId(
                          master_name, builder_name, build_number),
                  '_DummyModel', build_number)
    return _DummyModel(key=key)


class BaseModelTest(unittest.TestCase):
  def setUp(self):
    self.dummy_model = _DummyModel.Create('master', 'builder', 1)

  def testMasterName(self):
    self.assertEqual('master', self.dummy_model.master_name)

  def testBuilderName(self):
    self.assertEqual('builder', self.dummy_model.builder_name)

  def testBuildNumber(self):
    self.assertEqual(1, self.dummy_model.build_number)
