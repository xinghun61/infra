# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import infra.services.bugdroid.Issue as Issue


class ChangelistTest(unittest.TestCase):

  def setUp(self):
    self.cl = Issue.changelist()

  def test_append(self):
    self.cl.append('1')
    self.assertIn('1', self.cl.added)

  def test_remove(self):
    self.cl.append('1')
    self.cl.remove('1')
    self.assertNotIn('1', self.cl.added)

  def test_isChanged(self):
    self.cl.append('1')
    self.assertTrue(self.cl.isChanged())

  def test_reset(self):
    self.cl.append('1')
    self.cl.reset()
    self.assertEqual(0, len(self.cl.added))
    self.assertEqual(0, len(self.cl.removed))


class Issue2Test(unittest.TestCase):

  def setUp(self):
    self.issue = Issue.Issue2()

  def test_addLabel(self):
    self.issue.addLabel('pri-1')
    self.assertIn('pri-1', self.issue.labels)

  def test_removeLabel(self):
    self.issue.addLabel('pri-1')
    self.issue.removeLabel('pri-1')
    self.assertIn('-pri-1', self.issue.labels)
    self.assertNotIn('pri-1', self.issue.labels)

  def test_removeLabelByPrefix(self):
    self.issue.addLabel('pri-1')
    self.issue.removeLabelByPrefix('pri')
    self.assertNotIn('pri-1', self.issue.labels)

  def test_addCc(self):
    self.issue.addCc('user@example.com')
    self.assertIn('user@example.com', self.issue.cc)

  def test_removeCc(self):
    self.issue.addCc('user@example.com')
    self.issue.removeCc('user@example.com')
    self.assertNotIn('user@example.com', self.issue.cc)

  def test_getLabelsByPrefix(self):
    self.issue.addLabel('pri-1')
    self.issue.addLabel('test-1')
    res = self.issue.getLabelsByPrefix('pri')
    self.assertEqual(1, len(res))
    self.assertEqual('pri-1', res[0])

  def test_getLabelsContaining(self):
    self.issue.addLabel('releaseblock-m1')
    self.assertIn('releaseblock-m1',
                  self.issue.getLabelsContaining('releaseblock-.*'))

  def test_getLabelsMatching(self):
    self.issue.addLabel('pri-1')
    self.assertIn('pri-1',
                  self.issue.getLabelsMatching('pri-[01]'))

  def test_hasLabelContaining(self):
    self.issue.addLabel('releaseblock-m1')
    self.assertTrue(self.issue.hasLabelMatching('releaseblock-.*'))

  def test_hasLabelMatching(self):
    self.issue.addLabel('pri-1')
    self.assertTrue(self.issue.hasLabelMatching('pri-[01]'))

  def test_hasLabel(self):
    self.issue.addLabel('pri-1')
    self.assertTrue(self.issue.hasLabel('pri-1'))

  def test_HasCc(self):
    self.issue.addCc('user@example.com')
    self.assertTrue(self.issue.hasCc('user@example.com'))

  def test_getComments(self):
    pass
