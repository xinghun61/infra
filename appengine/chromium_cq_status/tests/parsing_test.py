#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from appengine.chromium_cq_status.shared import parsing

class TestCase(unittest.TestCase):
  def test_parse_project(self):
    self.assertEqual('chromium', parsing.parse_project(''))
    self.assertEqual('blink', parsing.parse_project('blink'))

  def test_parse_timestamp(self):
    self.assertEqual(None, parsing.parse_timestamp(''))
    self.assertEqual('1970-01-01 00:20:34',
        parsing.parse_timestamp('1234.56').strftime('%Y-%m-%d %H:%M:%S'))
    self.assertRaises(ValueError, lambda: parsing.parse_timestamp('invalid'))

  def test_parse_key(self):
    self.assertEqual(None, parsing.parse_key(''))
    self.assertEqual('test_key', parsing.parse_key('test_key'))
    self.assertRaises(ValueError, lambda: parsing.parse_key('1234'))
    self.assertRaises(ValueError, lambda: parsing.parse_key('1234L'))

  def test_parse_tags(self):
    self.assertEqual([], parsing.parse_tags(''))
    self.assertEqual(['test_tag'], parsing.parse_tags('test_tag'))
    self.assertEqual(['a', 'b', 'c'], parsing.parse_tags('a,b,c'))

  def test_parse_fields(self):
    self.assertEqual({}, parsing.parse_fields(''))
    self.assertEqual({"test": None, "this": [2, 3], "works": {}},
        parsing.parse_fields('{"test": null, "this": [2, 3], "works": {}}'))
    self.assertRaises(ValueError, lambda: parsing.parse_fields('not json'))
    self.assertRaises(ValueError,
        lambda: parsing.parse_fields('["not", "dict"]'))

  def test_parse_non_negative_integer(self):
    self.assertEqual(0, parsing.parse_non_negative_integer('0'))
    self.assertEqual(1234, parsing.parse_non_negative_integer('1234'))
    self.assertRaises(ValueError,
        lambda: parsing.parse_non_negative_integer(''))
    self.assertRaises(ValueError,
        lambda: parsing.parse_non_negative_integer('-1234'))

  def test_parse_cursor(self):
    self.assertEqual(None, parsing.parse_cursor(''))
    self.assertEqual('cursor_value', parsing.parse_cursor('cursor_value'))

  def test_use_default(self):
    def test_func(x):
      return x[0]
    default_func = parsing.use_default(test_func, 1234)
    self.assertEqual(1234, default_func(None))
    self.assertEqual(1234, default_func(''))
    self.assertEqual('1', default_func('1234'))

  def test_parse_request(self):
    self.assertEqual({
      'a': 'test_project',
      'b': None,
      'c': ['d', 'e', 'f'],
    }, parsing.parse_request({
      'a': 'test_project',
      'b': '',
      'c': 'd,e,f',
    }, {
      'a': parsing.parse_project,
      'b': parsing.parse_timestamp,
      'c': parsing.parse_tags,
    }))
    self.assertRaises(ValueError,
        lambda: parsing.parse_request({'a': '1234'}, {'a': parsing.parse_key}))

  def test_parse_url_tags(self):
    self.assertEqual([], parsing.parse_url_tags(None))
    self.assertEqual([], parsing.parse_url_tags(''))
    self.assertEqual(['test tag'], parsing.parse_url_tags('test tag'))
    self.assertEqual(['test tag'], parsing.parse_url_tags('/test tag/'))
    self.assertEqual(['tag1', 'tag2'], parsing.parse_url_tags('/tag1//tag2/'))

if __name__ == '__main__':
  unittest.main()
