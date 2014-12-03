# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import re

from google.appengine.ext import ndb

from test import CrBuildTestCase
import util


class TestEntity(ndb.Model, util.RegexIdMixin):
  ID_REGEX = re.compile('abc(\d\d)x')  # Example: abc123x

  def _pre_put_hook(self):
    self.validate_key()


class RegexIdMixinTestCase(CrBuildTestCase):
  def test_cannot_put_malformed_id(self):
    bad_id = 'sdkfsjf'
    entity = TestEntity(id=bad_id)
    self.assertEqual(entity.key.id(), bad_id)
    with self.assertRaises(util.BadIdError):
      entity.put()

  def test_put_with_good_id(self):
    good_id = 'abc12x'
    entity = TestEntity(id=good_id)
    self.assertEqual(entity.key.id(), good_id)
    entity.put()

  def test_no_key_is_bad_key(self):
    entity = TestEntity()
    self.assertIsNone(entity.key)
    with self.assertRaises(util.BadIdError):
      entity.put()

  def test_get_key_component(self):
    good_id = 'abc12x'
    entity = TestEntity(id=good_id)
    self.assertEqual(entity.get_key_component(0), '12')

    entity = TestEntity()
    self.assertIsNone(entity.key)
    self.assertEqual(entity.get_key_component(0), None)


class UtilTestCase(CrBuildTestCase):
  def test_datetime_to_timestamp(self):
    epoch = datetime(1970, 1, 1)
    self.assertEqual(util.datetime_to_timestamp(epoch), 0)

    # Test data provided by http://www.unixtimestamp.com
    expected = 1388534400
    actual = util.datetime_to_timestamp(datetime(2014, 1, 1))
    self.assertEqual(expected, actual)
