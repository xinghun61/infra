# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from parameterized import parameterized

from components import utils

from testing_utils import testing
import errors


class ErrorsTest(testing.AppengineTestCase):

  def test_validate_bucket_name(self):
    with self.assertRaises(errors.InvalidInputError):
      errors.validate_bucket_name(1)
    with self.assertRaises(errors.InvalidInputError):
      errors.validate_bucket_name('luci.x', project_id='y')
    with self.assertRaises(errors.InvalidInputError):
      errors.validate_bucket_name('')
    with self.assertRaises(errors.InvalidInputError):
      errors.validate_bucket_name('no spaces')
    with self.assertRaises(errors.InvalidInputError):
      errors.validate_bucket_name('no spaces')
    errors.validate_bucket_name('good-name')
    errors.validate_bucket_name('luci.infra.try', project_id='infra')

  def test_default_message(self):
    ex = errors.BuildIsCompletedError()
    self.assertEqual(ex.message, 'Build is complete and cannot be changed.')

  @parameterized.expand([
      ('a', None),
      ('', r'unspecified'),
      ('a' * 200, r'length is > 128'),
      ('#', r'invalid char\(s\)'),
  ])
  def test_validate_builder_name(self, name, error_pattern):
    if error_pattern:
      with self.assertRaisesRegexp(errors.InvalidInputError, error_pattern):
        errors.validate_builder_name(name)
    else:
      errors.validate_builder_name(name)


class ValidateLeaseExpirationDateTest(testing.AppengineTestCase):

  def setUp(self):
    super(ValidateLeaseExpirationDateTest, self).setUp()
    self.now = datetime.datetime(2018, 1, 1)
    self.patch('components.utils.utcnow', side_effect=lambda: self.now)

  def test_past(self):
    with self.assertRaises(errors.InvalidInputError):
      yesterday = utils.utcnow() - datetime.timedelta(days=1)
      errors.validate_lease_expiration_date(yesterday)

  def test_not_datetime(self):
    with self.assertRaises(errors.InvalidInputError):
      errors.validate_lease_expiration_date(1)

  def test_limit(self):
    with self.assertRaises(errors.InvalidInputError):
      dt = utils.utcnow() + datetime.timedelta(days=1)
      errors.validate_lease_expiration_date(dt)

  def test_none(self):
    errors.validate_lease_expiration_date(None)

  def test_valid(self):
    dt = utils.utcnow() + datetime.timedelta(minutes=5)
    errors.validate_lease_expiration_date(dt)
