# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.blame import Blame
from common.blame import Region

class BlameTest(unittest.TestCase):
  REGION1 = Region(1, 5, 'abc', 'a', 'a@email.com', '2014-08-14 19:38:42')
  REGION1_EXPECTED_JSON = {
      'start': 1,
      'count': 5,
      'revision': 'abc',
      'author_name': 'a',
      'author_email': 'a@email.com',
      'author_time': '2014-08-14 19:38:42'
  }

  REGION2 = Region(6, 10, 'def', 'b', 'b@email.com', '2014-08-19 19:38:42')
  REGION2_EXPECTED_JSON = {
      'start': 6,
      'count': 10,
      'revision': 'def',
      'author_name': 'b',
      'author_email': 'b@email.com',
      'author_time': '2014-08-19 19:38:42'
  }

  def testRegionToJson(self):
    self.assertEqual(self.REGION1_EXPECTED_JSON, self.REGION1.ToJson())
    self.assertEqual(self.REGION2_EXPECTED_JSON, self.REGION2.ToJson())

  def testBlameToJson(self):
    blame = Blame('def', 'a/c.cc')
    blame.AddRegion(self.REGION1)
    blame.AddRegion(self.REGION2)
    blame_json = blame.ToJson()
    self.assertEqual(3, len(blame_json))
    self.assertEqual('def', blame_json['revision'])
    self.assertEqual('a/c.cc', blame_json['path'])
    self.assertEqual(self.REGION1_EXPECTED_JSON, blame_json['regions'][0])
    self.assertEqual(self.REGION2_EXPECTED_JSON, blame_json['regions'][1])
