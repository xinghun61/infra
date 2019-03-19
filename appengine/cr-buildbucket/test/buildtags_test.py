# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import buildtags
import errors


class BuildsetTests(unittest.TestCase):

  def test_gitiles(self):
    buildtags.validate_buildset(
        'commit/gitiles/chromium.googlesource.com/chromium/src/+/'
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    )

  def test_gerrit(self):
    buildtags.validate_buildset(
        'patch/gerrit/chromium-review.googlesource.com/123/456'
    )

  def test_user_format(self):
    buildtags.validate_buildset('myformat/x')

  def test_invalid(self):
    bad = [
        (
            'commit/gitiles/chromium.googlesource.com/a/chromium/src/+/'
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        ),
        (
            'commit/gitiles/chromium.googlesource.com/chromium/src.git/+/'
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        ),
        'commit/gitiles/chromium.googlesource.com/chromium/src.git/+/aaaaaaaa',
        'patch/gerrit/chromium-review.googlesource.com/aa/bb',
        'a' * 2000,  # too long
    ]
    for bs in bad:
      with self.assertRaises(errors.InvalidInputError):
        buildtags.validate_buildset(bs)


class ValidateTagsTests(unittest.TestCase):

  def test_tags_none(self):
    self.assertIsNone(buildtags.validate_tags(None, 'search'))

  def test_nonlist(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags('tag:value', 'search')

  def test_nonstring(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['tag:value', 123456], 'search')

  def test_no_colon(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['tag,value'], 'search')

  def test_build_address(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['build_address:1'], 'new')
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['build_address:1'], 'append')

  def test_builder_inconsistent(self):
    err_pattern = r'conflicts with tag'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      buildtags.validate_tags(['builder:a', 'builder:b'], 'new')

  def test_builder_inconsistent_with_param(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['builder:a'], 'new', 'b')

  def test_append_builder(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['builder:1'], 'append')

  def test_no_key(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags([':'], 'search')

  def test_invalid_buildset(self):
    with self.assertRaises(errors.InvalidInputError):
      buildtags.validate_tags(['buildset:patch/gerrit/foo'], 'search')

  def test_two_gitiles_commits(self):
    err_pattern = r'More than one commits/gitiles buildset'
    with self.assertRaisesRegexp(errors.InvalidInputError, err_pattern):
      tags = [
          (
              'buildset:commit/gitiles/chromium.googlesource.com/chromium/src'
              '/+/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
          ),
          (
              'buildset:commit/gitiles/chromium.googlesource.com/chromium/src'
              '/+/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
          ),
      ]
      buildtags.validate_tags(tags, 'new')
