# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import json
import unittest

import webapp2

from ui_catalogue import routes_list
from ui_catalogue import ScreenshotLoader


class DummyScreenshotLoader(ScreenshotLoader):
  def get_data(self, data_location):
    if data_location == 'empty':
      return []
    return [{
      'filters': {
        'Screenshot Name': 'screenshot1',
        'f1': 'f1_a',
        'f2': 'f2_a'
      },
      'tags': [],
      'metadata': {
        'm1': 'm1_a'
      },
      'image_link': 'https://junk',
      'location': 'NotAFile'
    },
      {
        'filters': {
          'Screenshot Name': 'screenshot2',
          'f1': 'f1_a',
          'f2': 'f2_b',
          'f3': 'f3_a'
        },
        'tags': ['t1'],
        'metadata': {
          'm1': 'm1_a'
        },
        'image_link': 'file://rubbish',
        # Use the test source file as a dummy image, since we don't care about
        # its type or content, only that it is correctly read.
        'location': __file__
      }]


class UiCatalogueTest(unittest.TestCase):

  def setUp(self):
    self.app = webapp2.WSGIApplication(routes=routes_list, debug=True)
    self.app.config['screenshot_loader'] = DummyScreenshotLoader()

  def test_selector_list_empty(self):
    response = self.app.get_response(
        '/service/selector_list?screenshot_source=empty')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual({u'userTags':[], u'filters': {}},
                     json.loads(response.body))

  def test_selector_list_not_empty(self):
    response = self.app.get_response('/service/selector_list')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual({u'userTags': [u't1'],
                      u'filters': {u'Screenshot Name':
                                     [u'screenshot1', u'screenshot2'],
                                   u'f1': [u'f1_a'],
                                   u'f2': [u'f2_a', u'f2_b'],
                                   u'f3': [u'f3_a']}},
                     json.loads(response.body))

  def test_image_remote(self):
    response = self.app.get_response('/service/0/image')
    self.assertEqual(httplib.MOVED_PERMANENTLY, response.status_code)

  def test_image_local(self):
    response = self.app.get_response('/service/1/image')
    self.assertEqual(httplib.OK, response.status_code)
    with open(__file__) as f:
      self.assertEqual(f.read(), response.body)

  def test_data(self):
    response = self.app.get_response('/service/1/data')
    self.assertEqual({ 'filters': { 'Screenshot Name': 'screenshot2',
                                     'f1': 'f1_a',
                                     'f2': 'f2_b',
                                     'f3': 'f3_a'
                                     },
                       'userTags': ['t1'],
                       'metadata': {'m1': 'm1_a'}},
                     json.loads(response.body))

  def test_screenshot_list_all(self):
    response = self.app.get_response('/service/screenshot_list?filters={}')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual([{u'key': u'0', u'label': u'screenshot1'},
                      {u'key': u'1', u'label': u'screenshot2'}],
                     json.loads(response.body))

  def test_screenshot_list_simple_filter(self):
    response = self.app.get_response('/service/screenshot_list?filters=' +
                                     '{"Screenshot Name": "screenshot1" }')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual([{u'key': u'0', u'label': u'screenshot1'}],
                     json.loads(response.body))

  def test_screenshot_list_tag(self):
    response = self.app.get_response('/service/screenshot_list?filters={}&' +
                                     'userTags=t1')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual([{u'key': u'1', u'label': u'screenshot2'}],
                     json.loads(response.body))

  def test_screenshot_list_simple_no_match(self):
    response = self.app.get_response('/service/screenshot_list?filters='
                                     '{"Screenshot Name": "screenshot3" }')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual([], json.loads(response.body))

  def test_screenshot_list_complex_no_match(self):
    response = self.app.get_response('/service/screenshot_list?filters='
                                     '{"Screenshot Name": "screenshot1" }&' +
                                     'userTags=t1')
    self.assertEqual(httplib.OK, response.status_code)
    self.assertEqual([],
                     json.loads(response.body))
