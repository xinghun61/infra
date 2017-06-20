# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import infra.services.bugdroid.Comment as Comment


class CommentTest(unittest.TestCase):

  def setUp(self):
    self.comment = Comment.Comment()

  def test_hasLabelContaining(self):
    self.comment.labels = ['releaseblock-m1']
    self.assertTrue(self.comment.hasLabelContaining('releaseblock-.*'))
    self.assertFalse(self.comment.hasLabelContaining('merge-.*'))

  def test_getLabelsContaining(self):
    self.comment.labels = ['releaseblock-m1', 'merge-abc']
    self.assertEqual(self.comment.getLabelsContaining('releaseblock-.*')[0],
                     self.comment.labels[0])
    self.assertEqual(self.comment.getLabelsContaining('merge-.*')[0],
                     self.comment.labels[1])

  def test_hasLabelMatching(self):
    self.comment.labels = ['pri-1', 'merge-rejected']
    self.assertTrue(self.comment.hasLabelMatching('pri-[01]'))
    self.assertFalse(self.comment.hasLabelMatching('merge-requested'))

  def test_hasLabel(self):
    self.comment.labels = ['pri-1', 'merge-rejected']
    self.assertTrue(self.comment.hasLabel('PRI-1'))
    self.assertFalse(self.comment.hasLabel('pri-[01]'))