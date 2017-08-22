# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.appengine_testcase import AppengineTestCase
from scripts import grade_model


class GradeModelTest(AppengineTestCase):

  def testCommitUrlEquals(self):

    self.assertTrue(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/angle/angle.git/+/'
         'cccf2b0029b3e223f111594bbd4af054fb0b1fad'),
        ('https://chromium.googlesource.com/angle/angle.git/+/'
         'cccf2b0029b3e223f111594bbd4af054fb0b1fad')))

    self.assertTrue(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/chromium/src.git/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3'),
        ('https://chromium.googlesource.com/chromium/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3')))

    self.assertFalse(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/chromium/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3'),
        ('https://chromium.googlesource.com/chromium/src/+/'
         '7b1c46d4cb2783c9f12982b199a2ecfce334bb35')))

    self.assertFalse(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/chromium/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3'),
        ('https://chromium.googlesource.com/angle/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3')))


