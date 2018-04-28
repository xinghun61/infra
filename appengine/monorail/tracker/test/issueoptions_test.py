# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueoptions JSON feed."""

import mock
import unittest

import webapp2

from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueoptions


class IssueOptionsJSONTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        features=fake.FeaturesService())
    services.user.TestAddUser('user_111@domain.com', 111L)
    services.user.TestAddUser('user_222@domain.com', 222L)
    services.user.TestAddUser('user_333@domain.com', 333L)
    services.user.TestAddUser('user_666@domain.com', 666L)

    # User group 888 has members: user_555 and proj@monorail.com
    services.user.TestAddUser('group888@googlegroups.com', 888L)
    services.usergroup.TestAddGroupSettings(888L, 'group888@googlegroups.com')
    services.usergroup.TestAddMembers(888L, [555L, 1001L])

    # User group 999 has members: user_111 and user_444
    services.user.TestAddUser('group999@googlegroups.com', 999L)
    services.usergroup.TestAddGroupSettings(999L, 'group999@googlegroups.com')
    services.usergroup.TestAddMembers(999L, [111L, 444L])

    self.project = services.project.TestAddProject('proj')
    self.project.owner_ids.extend([111L])
    self.project.committer_ids.extend([222L])
    self.project.contributor_ids.extend([333L])
    self.servlet = issueoptions.IssueStatusLabelOptionsJSON(
        'req', webapp2.Response(), services=services)
    self.members_servlet = issueoptions.IssueMembersOptionsJSON(
        'req', webapp2.Response(), services=services)

    # Fake hotlists
    services.features.TestAddHotlist('name_111', owner_ids=[111L])
    services.features.TestAddHotlist('name_222', owner_ids=[222L])
    services.features.TestAddHotlist('name_333', owner_ids=[333L])
    services.features.TestAddHotlist('name_666', owner_ids=[666L])
    services.features.TestAddHotlist('name_999', owner_ids=[999L])

    self.services = services

  def RunHandleRequest(self, servlet, logged_in_user_id, perms,
                       effective_ids=None):
    mr = testing_helpers.MakeMonorailRequest(project=self.project, perms=perms)
    mr.auth.user_id = logged_in_user_id
    if effective_ids:
      mr.auth.effective_ids = effective_ids
    json_data = servlet.HandleRequest(mr)
    return json_data

  def RunAndGetMemberEmails(self, servlet, logged_in_user_id, perms,
                            effective_ids=None):
    json_data = self.RunHandleRequest(servlet,
        logged_in_user_id, perms, effective_ids=effective_ids)
    member_emails = [member['name'] for member in json_data['members']]
    return member_emails

  def VerifyMembersInFeeds(self, logged_in_user_id, perms, expected_visible):
    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        logged_in_user_id, perms)
    if expected_visible:
      self.assertEqual(
          ['user_111@domain.com', 'user_222@domain.com',
           'user_333@domain.com'],
          member_emails)
    else:
      self.assertEqual(
          ['user_111@domain.com', 'user_222@domain.com'],
          member_emails)

  def testHandleRequest_Normal(self):
    # Everyone can see everyone
    self.VerifyMembersInFeeds(
        111L, permissions.OWNER_ACTIVE_PERMISSIONSET, True)
    self.VerifyMembersInFeeds(
        222L, permissions.COMMITTER_ACTIVE_PERMISSIONSET, True)
    self.VerifyMembersInFeeds(
        333L, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET, True)

  def testHandleRequest_HideMembers(self):
    self.project.only_owners_see_contributors = True
    # Only project owners and committers can see everyone.
    self.VerifyMembersInFeeds(
        111L, permissions.OWNER_ACTIVE_PERMISSIONSET, True)
    self.VerifyMembersInFeeds(
        222L, permissions.COMMITTER_ACTIVE_PERMISSIONSET, True)
    self.VerifyMembersInFeeds(
        333L, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET, False)

  def testHandleRequest_MemberIsGroup(self):
    self.project.contributor_ids.extend([999L])
    json_data = self.RunHandleRequest(self.members_servlet,
        999L, permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    for member in json_data['members']:
      if member['name'] == 'group999@googlegroups.com':
        self.assertTrue(member['is_group'])
      else:
        self.assertNotIn('is_group', member)

  def testHandleRequest_AcExclusion(self):
    self.project.contributor_ids.extend([666L])

    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        666L, permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertIn('user_666@domain.com', member_emails)

    self.services.project.ac_exclusion_ids[self.project.project_id] = [666L]
    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        666L, permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertNotIn('user_666@domain.com', member_emails)

  def testHandleRequest_Hotlists(self):
    json_data = self.RunHandleRequest(self.servlet,
      111L, permissions.USER_PERMISSIONSET)
    self.assertListEqual(json_data['hotlists'],
                         [{'ref_str': 'name_111', 'summary': ''}])

  @unittest.skip('TODO(jrobbins): reimplement')
  def skip_testHandleRequest_Groups(self):
    self.project.contributor_ids.extend([888L, 999L])

    # User 111 can see 444 because they are both in the same user group,
    # and he can see 555 because of the project-is-a-member-of-group rule.
    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        111L, permissions.OWNER_ACTIVE_PERMISSIONSET,
        effective_ids={111L, 999L})
    self.assertIn('user_444@domain.com', member_emails)
    self.assertIn('user_555@domain.com', member_emails)

    # User 333 can see 555 because 555 is in a user group that includes
    # proj@monorail.com.
    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        333L, permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertTrue('user_555@domain.com' in member_emails)

    self.project.only_owners_see_contributors = True

    # User 111 can see 444 and 555, hub-and-spoke does not limit
    # project owners.
    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        111L, permissions.OWNER_ACTIVE_PERMISSIONSET,
        effective_ids={111L, 999L})
    self.assertTrue('user_444@domain.com' in member_emails)
    self.assertTrue('user_555@domain.com' in member_emails)

    # User 333 can no longer see 555 because the project-is-a-
    # member-of-group rule does not exend to contributors when
    # hub-and-spoke is set.  In that mode, contributors are not
    # supposed to know about all the other users.
    member_emails = self.RunAndGetMemberEmails(self.members_servlet,
        333L, permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertTrue('user_555@domain.com' in member_emails)

  def testHandleRequest_RestrictionLabels(self):
    json_data = self.RunHandleRequest(self.servlet,
        111L, permissions.OWNER_ACTIVE_PERMISSIONSET)
    labels = [lab['name'] for lab in json_data['labels']]
    self.assertIn('Restrict-View-EditIssue', labels)
    self.assertIn('Restrict-AddIssueComment-EditIssue', labels)
    self.assertIn('Restrict-View-CoreTeam', labels)


class GetOptionsTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        features=fake.FeaturesService(),
        usergroup=fake.UserGroupService())
    self.cnxn = None
    self.config = tracker_pb2.ProjectIssueConfig()
    self.services.config.StoreConfig(self.cnxn, self.config)
    self.config = self.services.config.GetProjectConfig(None, 789)
    self.project = self.services.project.TestAddProject('proj')
    self.mr = testing_helpers.MakeMonorailRequest(project=self.project)

  def testGetStatusOptions(self):
    self.config.well_known_statuses= [
      tracker_pb2.StatusDef(status='status1', means_open=True,
          status_docstring='docstring1'),
      tracker_pb2.StatusDef(status='status2', means_open=False,
          status_docstring='docstring2'),
    ]
    actual_open, actual_closed = issueoptions.GetStatusOptions(self.config)
    expected_open = [{'doc': 'docstring1', 'name': 'status1'}]
    expected_closed = [{'doc': 'docstring2', 'name': 'status2'}]
    self.assertEqual(expected_open, actual_open)
    self.assertEqual(expected_closed, actual_closed)

  def testGetComponentOptions(self):
    self.config.component_defs = [
      tracker_pb2.ComponentDef(component_id=123, project_id=789, path='Path',
          docstring='docstring', admin_ids=[111L], cc_ids=[], deprecated=False,
          label_ids=[])
    ]
    actual = issueoptions.GetComponentOptions(self.config)
    expected = [{'doc': 'docstring', 'name': 'Path'}]
    self.assertEqual(expected, actual)

  @mock.patch('tracker.tracker_helpers.LabelsNotMaskedByFields')
  def testGetLabelOptions(self, mockLabelsNotMaskedByFields):
    mockLabelsNotMaskedByFields.return_value = []
    custom_perms = []
    actual = issueoptions.GetLabelOptions(self.mr, self.config, custom_perms)
    expected = [
      {'doc': 'Only users who can edit the issue may access it',
       'name': 'Restrict-View-EditIssue'},
      {'doc': 'Only users who can edit the issue may add comments',
       'name': 'Restrict-AddIssueComment-EditIssue'},
      {'doc': 'Custom permission CoreTeam is needed to access',
       'name': 'Restrict-View-CoreTeam'}
    ]
    self.assertEqual(expected, actual)

  @mock.patch('testing.fake.FeaturesService.GetHotlistsByUserID')
  def testGetHotlistOptions(self, mockGetHotlistsByUserID):
    fake_hotlist = fake.Hotlist(hotlist_name='hotlist-1', hotlist_id=1)
    mockGetHotlistsByUserID.return_value = [fake_hotlist]
    actual = issueoptions.GetHotlistOptions(self.mr, self.services)
    expected = [{'ref_str': 'hotlist-1', 'summary': ''}]
    self.assertEqual(expected, actual)

  def testGetFieldOptions(self):
    self.config.field_defs = [
      tracker_pb2.FieldDef(field_id=1, project_id=789, field_name='FieldName',
          field_type=tracker_pb2.FieldTypes.INT_TYPE)
    ]
    actual = issueoptions.GetFieldOptions(self.mr, self.services, self.config,
        [], [])
    expected =  [{
      'choices': [],
     'docstring': None,
     'field_id': 1,
     'field_name': 'FieldName',
     'field_type': 2,
     'is_multivalued': False,
     'is_required': False,
     'needs_perm': None
    }]
    self.assertEqual(expected, actual)


class FilterMemberDataTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService())
    self.owner_email = 'owner@dom.com'
    self.committer_email = 'commit@dom.com'
    self.contributor_email = 'contrib@dom.com'
    self.indirect_member_email = 'ind@dom.com'
    self.all_emails = [self.owner_email, self.committer_email,
                       self.contributor_email, self.indirect_member_email]
    self.project = services.project.TestAddProject('proj')

  def DoFiltering(self, perms, unsigned_user=False):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=perms)
    if not unsigned_user:
      mr.auth.user_id = 111L
      mr.auth.user_view = testing_helpers.Blank(domain='jrobbins.org')
    return issueoptions._FilterMemberData(
        mr, [self.owner_email], [self.committer_email],
        [self.contributor_email], [self.indirect_member_email])

  def testUnsignedUser_NormalProject(self):
    visible_members = self.DoFiltering(
        permissions.READ_ONLY_PERMISSIONSET, unsigned_user=True)
    self.assertItemsEqual(
        [self.owner_email, self.committer_email, self.contributor_email,
         self.indirect_member_email],
        visible_members)

  def testUnsignedUser_RestrictedProject(self):
    self.project.only_owners_see_contributors = True
    visible_members = self.DoFiltering(
        permissions.READ_ONLY_PERMISSIONSET, unsigned_user=True)
    self.assertItemsEqual(
        [self.owner_email, self.committer_email, self.indirect_member_email],
        visible_members)

  def testOwnersAndAdminsCanSeeAll_NormalProject(self):
    visible_members = self.DoFiltering(
        permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.ADMIN_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

  def testOwnersAndAdminsCanSeeAll_HubAndSpoke(self):
    self.project.only_owners_see_contributors = True

    visible_members = self.DoFiltering(
        permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.ADMIN_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

  def testNonOwnersCanSeeAll_NormalProject(self):
    visible_members = self.DoFiltering(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

  def testCommittersSeeOnlySameDomain_HubAndSpoke(self):
    self.project.only_owners_see_contributors = True

    visible_members = self.DoFiltering(
        permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(
        [self.owner_email, self.committer_email, self.indirect_member_email],
        visible_members)


class BuildRestrictionChoicesTest(unittest.TestCase):

  def testBuildRestrictionChoices(self):
    project = project_pb2.Project()
    choices = issueoptions._BuildRestrictionChoices(project, [], [])
    self.assertEquals([], choices)

    choices = issueoptions._BuildRestrictionChoices(
        project, [], ['Hop', 'Jump'])
    self.assertEquals([], choices)

    freq = [('View', 'B', 'You need permission B to do anything'),
            ('A', 'B', 'You need B to use A')]
    choices = issueoptions._BuildRestrictionChoices(project, freq, [])
    expected = [dict(name='Restrict-View-B',
                     doc='You need permission B to do anything'),
                dict(name='Restrict-A-B',
                     doc='You need B to use A')]
    self.assertListEqual(expected, choices)

    extra_perms = project_pb2.Project.ExtraPerms(
        perms=['Over18', 'Over21'])
    project.extra_perms.append(extra_perms)
    choices = issueoptions._BuildRestrictionChoices(
        project, [], ['Drink', 'Smoke'])
    expected = [dict(name='Restrict-Drink-Over18',
                     doc='Permission Over18 needed to use Drink'),
                dict(name='Restrict-Drink-Over21',
                     doc='Permission Over21 needed to use Drink'),
                dict(name='Restrict-Smoke-Over18',
                     doc='Permission Over18 needed to use Smoke'),
                dict(name='Restrict-Smoke-Over21',
                     doc='Permission Over21 needed to use Smoke')]
    self.assertListEqual(expected, choices)
