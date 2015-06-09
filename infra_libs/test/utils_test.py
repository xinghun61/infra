# -*- encoding: utf-8 -*-
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import unittest

import infra_libs


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

class ReadJsonTest(unittest.TestCase):
  def test_read_from_file(self):
    new_dict = infra_libs.read_json_as_utf8(
      filename=os.path.join(DATA_DIR, 'utils_test_dict.json'))

    # Make sure all keys can be decoded as utf8
    for key in new_dict.iterkeys():
      self.assertIsInstance(key, str)
      key.decode('utf-8')  # should raise no exceptions

    # Make sure all values contain only utf8
    self.assertIsInstance(new_dict['string'], str)
    new_dict['string'].decode('utf-8')

    for value in new_dict['list_of_strings']:
      self.assertIsInstance(value, str)
      value.decode('utf-8')

    sub_dict = new_dict['clé accentuée']
    for key, value in sub_dict.iteritems():
      self.assertIsInstance(key, str)
      self.assertIsInstance(value, str)

      key.decode('utf-8')
      value.decode('utf-8')

  def test_read_from_string(self):
    orig_dict = {"string": "prêt¿",
                 "list_of_strings": ["caractères", "accentués", "nous voilà"],
                 "clé accentuée": {"clé": "privée", "vie": "publique"},
               }

    json_data = json.dumps(orig_dict)
    new_dict = infra_libs.read_json_as_utf8(text=json_data)

    self.assertEqual(orig_dict, new_dict)

    # Make sure all keys can be decoded as utf8
    for key in new_dict.iterkeys():
      self.assertIsInstance(key, str)
      key.decode('utf-8')  # should raise no exceptions

    # Make sure all values contain only utf8
    self.assertIsInstance(new_dict['string'], str)
    new_dict['string'].decode('utf-8')

    for value in new_dict['list_of_strings']:
      self.assertIsInstance(value, str)
      value.decode('utf-8')

    sub_dict = new_dict['clé accentuée']
    for key, value in sub_dict.iteritems():
      self.assertIsInstance(key, str)
      self.assertIsInstance(value, str)

      key.decode('utf-8')
      value.decode('utf-8')

  def test_read_from_string_no_unicode(self):
    # only numerical value. Keys have to be string in json.
    orig_dict = {'1': 2,
                 '3': [4, 5., 7, None],
                 '7':{'8': 9, '10': 11}}
    json_data = json.dumps(orig_dict)
    new_dict = infra_libs.read_json_as_utf8(text=json_data)
    self.assertEqual(orig_dict, new_dict)

  def test_dict_in_dict(self):
    orig_dict = {'à': {'présent': {'ça': 'prétend marcher.'}}}
    json_data = json.dumps(orig_dict)
    new_dict = infra_libs.read_json_as_utf8(text=json_data)
    self.assertEqual(orig_dict, new_dict)

  def test_dict_in_list(self):
    orig_dict = ['à', {'présent': {'ça': 'prétend marcher.'}}]
    json_data = json.dumps(orig_dict)
    new_dict = infra_libs.read_json_as_utf8(text=json_data)
    self.assertEqual(orig_dict, new_dict)

  def test_error_with_two_arguments(self):
    with self.assertRaises(ValueError):
      infra_libs.read_json_as_utf8(filename='filename', text='{}')

  def test_error_with_no_arguments(self):
    with self.assertRaises(ValueError):
      infra_libs.read_json_as_utf8()
