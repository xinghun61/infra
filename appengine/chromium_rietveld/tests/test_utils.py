#!/usr/bin/env python
# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for utils."""

import unittest

import setup
setup.process_args()

from codereview import utils


class UtilsTest(unittest.TestCase):
  def test_parse_cq_status_url_message_v2(self):
    url = ('https://chromium-cq-status.appspot.com/v2/'
           'patch-status/codereview.chromium.org/213/1')
    msg = 'CQ is trying da patch. Follow status at\n' + url
    self.assertEqual(utils.parse_cq_status_url_message(msg), (url, 213, 1))
    msg += '\n'
    self.assertEqual(utils.parse_cq_status_url_message(msg), (url, 213, 1))
    msg = 'Dry run: ' + msg
    self.assertEqual(utils.parse_cq_status_url_message(msg), (url, 213, 1))

  def test_parse_cq_status_url_message_v1(self):
    url = 'https://chromium-cq-status.appspot.com/patch-status/213/1'
    msg = 'CQ is trying da patch. Follow status at\n' + url
    self.assertEqual(utils.parse_cq_status_url_message(msg), (url, 213, 1))
    msg += '\n'
    self.assertEqual(utils.parse_cq_status_url_message(msg), (url, 213, 1))
    msg = 'Dry run: ' + msg
    self.assertEqual(utils.parse_cq_status_url_message(msg), (url, 213, 1))

  def test_parse_cq_status_url_message_fail(self):
    self.assertEqual(utils.parse_cq_status_url_message(''), (None, None, None))
    msg = 'Dry run failed because https://weird.url/patch-status/123/4'
    self.assertEqual(utils.parse_cq_status_url_message(msg), (None, None, None))


if __name__ == '__main__':
  unittest.main()
