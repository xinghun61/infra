# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.appengine_testcase import AppengineTestCase
from scripts import grade_model


class GradeModelTest(AppengineTestCase):

  def testGetCommitKeyFromUrl(self):
    self.assertEqual(
        grade_model.GetCommitKeyFromUrl(
          'https://chromium.googlesource.com/chromium/src/+/ff0a4a3f4f165290c3da7902a67d98434a49e7e3'), # pylint: disable=line-too-long
        'ff0a4a3f4f165290c3da7902a67d98434a49e7e3')

    self.assertEqual(
        grade_model.GetCommitKeyFromUrl(
          'https://chromium.googlesource.com/chromium/src.git/+/7b1c46d4cb2783c9f12982b199a2ecfce334bb35'), # pylint: disable=line-too-long
        '7b1c46d4cb2783c9f12982b199a2ecfce334bb35')

    with self.assertRaises(AssertionError):
      grade_model.GetCommitKeyFromUrl('https://www.google.com/')
