#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from appengine_module.chromium_cq_status.shared import parsing


class TestCase(unittest.TestCase):
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

  def test_parse_string(self):
    self.assertEqual('', parsing.parse_string(None))
    self.assertEqual('project_name', parsing.parse_string('project_name'))
    self.assertEqual('a,b,c', parsing.parse_string('a,b,c'))

  def test_parse_strings(self):
    self.assertEqual([], parsing.parse_strings(''))
    self.assertEqual(['test_tag'], parsing.parse_strings('test_tag'))
    self.assertEqual(['a', 'b', 'c'], parsing.parse_strings('a,b,c'))

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

  def test_parse_query_count(self):
    self.assertEqual(100, parsing.parse_query_count(''))
    self.assertEqual(0, parsing.parse_query_count('0'))
    self.assertEqual(123, parsing.parse_query_count('123'))
    self.assertEqual(1000, parsing.parse_query_count('1234'))
    self.assertRaises(ValueError,
        lambda: parsing.parse_non_negative_integer('pants'))
    self.assertRaises(ValueError,
        lambda: parsing.parse_non_negative_integer('-123'))

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
      'a': None,
      'b': ['a', 'b', 'c'],
      'c': {'d': 'e'},
    }, parsing.parse_request(MockRequest({
      'a': '',
      'b': 'a,b,c',
      'c': '{"d": "e"}',
    }), {
      'a': parsing.parse_timestamp,
      'b': parsing.parse_strings,
      'c': parsing.parse_fields,
    }))
    self.assertRaises(ValueError, lambda: parsing.parse_request(
        MockRequest({'a': '1234'}),
        {'a': parsing.parse_key}))
    self.assertRaises(ValueError, lambda: parsing.parse_request(
        MockRequest({'a': 'valid', 'b': 'invalid'}),
        {'a': parsing.parse_key}))

  def test_parse_url_tags(self):
    self.assertEqual([], parsing.parse_url_tags(None))
    self.assertEqual([], parsing.parse_url_tags(''))
    self.assertEqual(['test tag'], parsing.parse_url_tags('test tag'))
    self.assertEqual(['test tag'], parsing.parse_url_tags('/test tag/'))
    self.assertEqual(['tag1', 'tag2'], parsing.parse_url_tags('/tag1//tag2/'))

class MockRequest(object):
  def __init__(self, parameters):
    self.parameters = parameters

  def get(self, key):
    return self.parameters.get(key, '')

  def arguments(self):
    return self.parameters.keys()
