# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for monorail.framework.framework_bizobj."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import mock

import settings
from framework import framework_bizobj
from framework import framework_constants
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from tracker import tracker_bizobj


class ArtifactTest(unittest.TestCase):

  def setUp(self):
    # No custom fields.  Exclusive prefixes: Type, Priority, Milestone.
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testMergeLabels_Labels(self):
    # Empty case.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        [], [], [], self.config)
    self.assertEquals(merged_labels, [])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, [])

    # No-op case.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['a', 'b'], [], [], self.config)
    self.assertEquals(merged_labels, ['a', 'b'])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, [])

    # Adding and removing at the same time.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['a', 'b', 'd'], ['c'], ['d'], self.config)
    self.assertEquals(merged_labels, ['a', 'b', 'c'])
    self.assertEquals(update_add, ['c'])
    self.assertEquals(update_remove, ['d'])

    # Removing a non-matching label has no effect.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['a', 'b', 'd'], ['d'], ['e'], self.config)
    self.assertEquals(merged_labels, ['a', 'b', 'd'])
    self.assertEquals(update_add, [])     # d was already there.
    self.assertEquals(update_remove, [])  # there was no e.

    # We can add and remove at the same time.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], ['Hot'], ['OpSys-OSX'], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium', 'Hot'])
    self.assertEquals(update_add, ['Hot'])
    self.assertEquals(update_remove, ['OpSys-OSX'])

    # Adding Priority-High replaces Priority-Medium.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], ['Priority-High', 'OpSys-Win'], [],
        self.config)
    self.assertEquals(merged_labels,
                      ['OpSys-OSX', 'Priority-High', 'OpSys-Win'])
    self.assertEquals(update_add, ['Priority-High', 'OpSys-Win'])
    self.assertEquals(update_remove, [])

    # Adding Priority-High and Priority-Low replaces with High only.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'],
        ['Priority-High', 'Priority-Low'], [], self.config)
    self.assertEquals(merged_labels,
                      ['OpSys-OSX', 'Priority-High'])
    self.assertEquals(update_add, ['Priority-High'])
    self.assertEquals(update_remove, [])

    # Removing a mix of matching and non-matching labels only does matching.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], [], ['Priority-Medium', 'OpSys-Win'],
        self.config)
    self.assertEquals(merged_labels, ['OpSys-OSX'])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, ['Priority-Medium'])

    # Multi-part labels work as expected.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX-11'],
        ['Priority-Medium-Rare', 'OpSys-OSX-13'], [], self.config)
    self.assertEquals(
        merged_labels, ['OpSys-OSX-11', 'Priority-Medium-Rare', 'OpSys-OSX-13'])
    self.assertEquals(update_add, ['Priority-Medium-Rare', 'OpSys-OSX-13'])
    self.assertEquals(update_remove, [])

    # Multi-part exclusive prefixes only filter labels that match whole prefix.
    self.config.exclusive_label_prefixes.append('Branch-Name')
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Branch-Name-Master'],
        ['Branch-Prediction', 'Branch-Name-Beta'], [], self.config)
    self.assertEquals(
        merged_labels, ['Branch-Prediction', 'Branch-Name-Beta'])
    self.assertEquals(update_add, ['Branch-Prediction', 'Branch-Name-Beta'])
    self.assertEquals(update_remove, [])

  def testMergeLabels_SingleValuedEnums(self):
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=1, field_name='Size',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        is_multivalued=False))
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=1, field_name='Branch-Name',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        is_multivalued=False))

    # We can add a label for a single-valued enum.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], ['Size-L'], [], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium', 'OpSys-OSX', 'Size-L'])
    self.assertEquals(update_add, ['Size-L'])
    self.assertEquals(update_remove, [])

    # Adding and removing the same label adds it.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium'], ['Size-M'], ['Size-M'], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium', 'Size-M'])
    self.assertEquals(update_add, ['Size-M'])
    self.assertEquals(update_remove, [])

    # Adding Size-L replaces Size-M.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'Size-M'], ['Size-L', 'OpSys-Win'], [],
        self.config)
    self.assertEquals(merged_labels,
                      ['Priority-Medium', 'Size-L', 'OpSys-Win'])
    self.assertEquals(update_add, ['Size-L', 'OpSys-Win'])
    self.assertEquals(update_remove, [])

    # Adding Size-L and Size-XL replaces with L only.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Size-M', 'OpSys-OSX'], ['Size-L', 'Size-XL'], [], self.config)
    self.assertEquals(merged_labels, ['OpSys-OSX', 'Size-L'])
    self.assertEquals(update_add, ['Size-L'])
    self.assertEquals(update_remove, [])

    # Multi-part labels work as expected.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Size-M', 'OpSys-OSX'], ['Size-M-USA'], [], self.config)
    self.assertEquals(
        merged_labels, ['OpSys-OSX', 'Size-M-USA'])
    self.assertEquals(update_add, ['Size-M-USA'])
    self.assertEquals(update_remove, [])

    # Multi-part enum names only filter labels that match whole name.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Branch-Name-Master'],
        ['Branch-Prediction', 'Branch-Name-Beta'], [], self.config)
    self.assertEquals(
        merged_labels, ['Branch-Prediction', 'Branch-Name-Beta'])
    self.assertEquals(update_add, ['Branch-Prediction', 'Branch-Name-Beta'])
    self.assertEquals(update_remove, [])

  def testMergeLabels_MultiValuedEnums(self):
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=1, field_name='OpSys',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        is_multivalued=True))
    self.config.field_defs.append(tracker_pb2.FieldDef(
        field_id=1, field_name='Branch-Name',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE,
        is_multivalued=True))

    # We can add a label for a multi-valued enum.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium'], ['OpSys-Win'], [], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium', 'OpSys-Win'])
    self.assertEquals(update_add, ['OpSys-Win'])
    self.assertEquals(update_remove, [])

    # We can remove a matching label for a multi-valued enum.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-Win'], [], ['OpSys-Win'], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium'])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, ['OpSys-Win'])

    # We can remove a non-matching label and it is a no-op.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], [], ['OpSys-Win'], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium', 'OpSys-OSX'])
    self.assertEquals(update_add, [])
    self.assertEquals(update_remove, [])

    # Adding and removing the same label adds it.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium'], ['OpSys-Win'], ['OpSys-Win'], self.config)
    self.assertEquals(merged_labels, ['Priority-Medium', 'OpSys-Win'])
    self.assertEquals(update_add, ['OpSys-Win'])
    self.assertEquals(update_remove, [])

    # We can add a label for a multi-valued enum, even if matching exists.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Priority-Medium', 'OpSys-OSX'], ['OpSys-Win'], [], self.config)
    self.assertEquals(
        merged_labels, ['Priority-Medium', 'OpSys-OSX', 'OpSys-Win'])
    self.assertEquals(update_add, ['OpSys-Win'])
    self.assertEquals(update_remove, [])

    # Adding two at the same time is fine.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Size-M', 'OpSys-OSX'], ['OpSys-Win', 'OpSys-Vax'], [], self.config)
    self.assertEquals(
        merged_labels, ['Size-M', 'OpSys-OSX', 'OpSys-Win', 'OpSys-Vax'])
    self.assertEquals(update_add, ['OpSys-Win', 'OpSys-Vax'])
    self.assertEquals(update_remove, [])

    # Multi-part labels work as expected.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Size-M', 'OpSys-OSX'], ['OpSys-Win-10'], [], self.config)
    self.assertEquals(
        merged_labels, ['Size-M', 'OpSys-OSX', 'OpSys-Win-10'])
    self.assertEquals(update_add, ['OpSys-Win-10'])
    self.assertEquals(update_remove, [])

    # Multi-part enum names don't mess up anything.
    (merged_labels, update_add, update_remove) = framework_bizobj.MergeLabels(
        ['Branch-Name-Master'],
        ['Branch-Prediction', 'Branch-Name-Beta'], [], self.config)
    self.assertEquals(
        merged_labels,
        ['Branch-Name-Master', 'Branch-Prediction', 'Branch-Name-Beta'])
    self.assertEquals(update_add, ['Branch-Prediction', 'Branch-Name-Beta'])
    self.assertEquals(update_remove, [])


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


class ValidatePrefTest(unittest.TestCase):

  def testUnknown(self):
    msg = framework_bizobj.ValidatePref('shoe_size', 'true')
    self.assertIn('shoe_size', msg)
    self.assertIn('Unknown', msg)

    msg = framework_bizobj.ValidatePref('', 'true')
    self.assertIn('Unknown', msg)

  def testTooLong(self):
    msg = framework_bizobj.ValidatePref('code_font', 'x' * 100)
    self.assertIn('code_font', msg)
    self.assertIn('too long', msg)

  def testKnownValid(self):
    self.assertIsNone(framework_bizobj.ValidatePref('code_font', 'true'))
    self.assertIsNone(framework_bizobj.ValidatePref('code_font', 'false'))

  def testKnownInvalid(self):
    msg = framework_bizobj.ValidatePref('code_font', '')
    self.assertIn('Invalid', msg)

    msg = framework_bizobj.ValidatePref('code_font', 'sometimes')
    self.assertIn('Invalid', msg)


class IsCorpUserTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    self.services.user.TestAddUser('corp_user@example.com', 111L)
    self.services.user.TestAddUser('corp_group@example.com', 888L)
    self.services.usergroup.TestAddGroupSettings(888L, 'corp_group@example.com')

  @mock.patch('settings.corp_mode_user_groups', [])
  def testNoCorpGroups(self):
    """We handle the case where no corp user groups are defined."""
    self.assertFalse(
        framework_bizobj.IsCorpUser(self.cnxn, self.services, 111L))

  @mock.patch('settings.corp_mode_user_groups', ['corp_group@example.com'])
  def testNonCorpUser(self):
    """We detect when a user is not part of a corp user group."""
    self.assertFalse(
        framework_bizobj.IsCorpUser(self.cnxn, self.services, 111L))

  @mock.patch('settings.corp_mode_user_groups', ['corp_group@example.com'])
  def testCorpUser(self):
    """We detect when a user is a member of such a group."""
    self.services.usergroup.TestAddMembers(888L, [111L, 222L])
    self.assertTrue(
        framework_bizobj.IsCorpUser(self.cnxn, self.services, 111L))
