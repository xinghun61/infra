# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for monorail.framework.framework_bizobj."""

import unittest

from framework import framework_bizobj
from framework import framework_constants
from proto import project_pb2


class ArtifactTest(unittest.TestCase):

  def testMergeLabels(self):
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        [], [], [], [])
    self.assertEquals(merged_labels, [])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, [])

    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['a', 'b'], [], [], [])
    self.assertEquals(merged_labels, ['a', 'b'])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, [])

    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['a', 'b', 'd'], ['c'], ['d'], [])
    self.assertEquals(merged_labels, ['a', 'b', 'c'])
    self.assertEquals(update_add, ['c'])
    self.assertEquals(update_remove, ['d'])

    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['a', 'b', 'd'], ['d'], ['e'], [])
    self.assertEquals(merged_labels, ['a', 'b', 'd'])
    self.assertEquals(update_add, [])     # d was already there.
    self.assertEquals(update_remove, [])  # there was no e.

    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], ['Hot'], ['OpSys-OSX'], ['Priority'])
    self.assertEquals(merged_labels, ['Priority-Medium', 'Hot'])
    self.assertEquals(update_add, ['Hot'])
    self.assertEquals(update_remove, ['OpSys-OSX'])

    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], ['Priority-High', 'OpSys-Win'], [],
        ['Priority'])
    self.assertEquals(merged_labels,
                      ['OpSys-OSX', 'Priority-High', 'OpSys-Win'])
    self.assertEquals(update_add, ['Priority-High', 'OpSys-Win'])
    self.assertEquals(update_remove, [])

    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], [], ['Priority-Medium', 'OpSys-Win'],
        ['Priority'])
    self.assertEquals(merged_labels, ['OpSys-OSX'])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, ['Priority-Medium'])


class CanonicalizeLabelTest(unittest.TestCase):

  def testCanonicalizeLabel(self):
    self.assertEqual(None, framework_bizobj.CanonicalizeLabel(None))
    self.assertEqual('FooBar', framework_bizobj.CanonicalizeLabel('Foo  Bar '))
    self.assertEqual('Foo.Bar',
                     framework_bizobj.CanonicalizeLabel('Foo . Bar '))
    self.assertEqual('Foo-Bar',
                     framework_bizobj.CanonicalizeLabel('Foo - Bar '))


class IsValidProjectNameTest(unittest.TestCase):

  def testBadChars(self):
    self.assertFalse(framework_bizobj.IsValidProjectName('spa ce'))
    self.assertFalse(framework_bizobj.IsValidProjectName('under_score'))
    self.assertFalse(framework_bizobj.IsValidProjectName('name.dot'))
    self.assertFalse(framework_bizobj.IsValidProjectName('pie#sign$'))
    self.assertFalse(framework_bizobj.IsValidProjectName('(who?)'))

  def testBadHyphen(self):
    self.assertFalse(framework_bizobj.IsValidProjectName('name-'))
    self.assertFalse(framework_bizobj.IsValidProjectName('-name'))
    self.assertTrue(framework_bizobj.IsValidProjectName('project-name'))

  def testMinimumLength(self):
    self.assertFalse(framework_bizobj.IsValidProjectName('x'))
    self.assertTrue(framework_bizobj.IsValidProjectName('xy'))

  def testMaximumLength(self):
    self.assertFalse(framework_bizobj.IsValidProjectName(
        'x' * (framework_constants.MAX_PROJECT_NAME_LENGTH + 1)))
    self.assertTrue(framework_bizobj.IsValidProjectName(
        'x' * (framework_constants.MAX_PROJECT_NAME_LENGTH)))

  def testInvalidName(self):
    self.assertFalse(framework_bizobj.IsValidProjectName(''))
    self.assertFalse(framework_bizobj.IsValidProjectName('000'))

  def testValidName(self):
    self.assertTrue(framework_bizobj.IsValidProjectName('098asd'))
    self.assertTrue(framework_bizobj.IsValidProjectName('one-two-three'))


class UserIsInProjectTest(unittest.TestCase):

  def testUserIsInProject(self):
    p = project_pb2.Project()
    self.assertFalse(framework_bizobj.UserIsInProject(p, {10}))
    self.assertFalse(framework_bizobj.UserIsInProject(p, set()))

    p.owner_ids.extend([1, 2, 3])
    p.committer_ids.extend([4, 5, 6])
    p.contributor_ids.extend([7, 8, 9])
    self.assertTrue(framework_bizobj.UserIsInProject(p, {1}))
    self.assertTrue(framework_bizobj.UserIsInProject(p, {4}))
    self.assertTrue(framework_bizobj.UserIsInProject(p, {7}))
    self.assertFalse(framework_bizobj.UserIsInProject(p, {10}))

    # Membership via group membership
    self.assertTrue(framework_bizobj.UserIsInProject(p, {10, 4}))

    # Membership via several group memberships
    self.assertTrue(framework_bizobj.UserIsInProject(p, {1, 4}))

    # Several irrelevant group memberships
    self.assertFalse(framework_bizobj.UserIsInProject(p, {10, 11, 12}))


class AllProjectMembersTest(unittest.TestCase):

  def testAllProjectMembers(self):
    p = project_pb2.Project()
    self.assertEqual(framework_bizobj.AllProjectMembers(p), [])

    p.owner_ids.extend([1, 2, 3])
    p.committer_ids.extend([4, 5, 6])
    p.contributor_ids.extend([7, 8, 9])
    self.assertEqual(framework_bizobj.AllProjectMembers(p),
                     [1, 2, 3, 4, 5, 6, 7, 8, 9])


if __name__ == '__main__':
  unittest.main()
