# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for framework_views classes."""

import unittest

from framework import framework_views
from framework import monorailrequest
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
import settings


LONG_STR = 'VeryLongStringThatCertainlyWillNotFit'
LONG_PART_STR = 'OnePartThatWillNotFit-OneShort'


class LabelViewTest(unittest.TestCase):

  def testLabelView(self):
    view = framework_views.LabelView('', None)
    self.assertEquals('', view.name)

    view = framework_views.LabelView('Priority-High', None)
    self.assertEquals('Priority-High', view.name)
    self.assertIsNone(view.is_restrict)
    self.assertEquals('', view.docstring)
    self.assertEquals('Priority', view.prefix)
    self.assertEquals('High', view.value)

    view = framework_views.LabelView('%s-%s' % (LONG_STR, LONG_STR), None)
    self.assertEquals('%s-%s' % (LONG_STR, LONG_STR), view.name)
    self.assertEquals('', view.docstring)
    self.assertEquals(LONG_STR, view.prefix)
    self.assertEquals(LONG_STR, view.value)

    view = framework_views.LabelView(LONG_PART_STR, None)
    self.assertEquals(LONG_PART_STR, view.name)
    self.assertEquals('', view.docstring)
    self.assertEquals('OnePartThatWillNotFit', view.prefix)
    self.assertEquals('OneShort', view.value)

    config = tracker_pb2.ProjectIssueConfig()
    config.well_known_labels.append(tracker_pb2.LabelDef(
        label='Priority-High', label_docstring='Must ship in this milestone'))

    view = framework_views.LabelView('Priority-High', config)
    self.assertEquals('Must ship in this milestone', view.docstring)

    view = framework_views.LabelView('Priority-Foo', config)
    self.assertEquals('', view.docstring)

    view = framework_views.LabelView('Restrict-View-Commit', None)
    self.assertTrue(view.is_restrict)


class StatusViewTest(unittest.TestCase):

  def testStatusView(self):
    view = framework_views.StatusView('', None)
    self.assertEquals('', view.name)

    view = framework_views.StatusView('Accepted', None)
    self.assertEquals('Accepted', view.name)
    self.assertEquals('', view.docstring)
    self.assertEquals('yes', view.means_open)

    view = framework_views.StatusView(LONG_STR, None)
    self.assertEquals(LONG_STR, view.name)
    self.assertEquals('', view.docstring)
    self.assertEquals('yes', view.means_open)

    config = tracker_pb2.ProjectIssueConfig()
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='SlamDunk', status_docstring='Code fixed and taught a lesson',
        means_open=False))

    view = framework_views.StatusView('SlamDunk', config)
    self.assertEquals('Code fixed and taught a lesson', view.docstring)
    self.assertFalse(view.means_open)

    view = framework_views.StatusView('SlammedBack', config)
    self.assertEquals('', view.docstring)


class RevealEmailsToMembersTest(unittest.TestCase):

  def setUp(self):
    project = project_pb2.Project()
    project.owner_ids.append(111L)
    project.committer_ids.append(222L)
    project.contributor_ids.append(333L)
    project.contributor_ids.append(888L)
    user = user_pb2.User()
    user.is_site_admin = False
    self.mr = monorailrequest.MonorailRequest()
    self.mr.project = project
    self.mr.auth.user_pb = user

  def CheckRevealAllToMember(
      self, logged_in_user_id, expected, viewed_user_id=333L, group_id=None):
    user_view = framework_views.UserView(
        viewed_user_id, 'user@example.com', True)

    if group_id:
      pass  # xxx re-implement groups

    users_by_id = {333L: user_view}
    self.mr.auth.user_id = logged_in_user_id
    self.mr.auth.effective_ids = {logged_in_user_id}
    # Assert display name is obscured before the reveal.
    self.assertEqual('u...@example.com', user_view.display_name)
    # Assert profile url contains user ID before the reveal.
    self.assertEqual('/u/%s/' % viewed_user_id, user_view.profile_url)
    framework_views.RevealAllEmailsToMembers(self.mr, users_by_id)
    self.assertEqual(expected, not user_view.obscure_email)
    if expected:
      # Assert display name is now revealed.
      self.assertEqual('user@example.com', user_view.display_name)
      # Assert profile url contains the email.
      self.assertEqual('/u/user@example.com/', user_view.profile_url)
    else:
      # Assert display name is still hidden.
      self.assertEqual('u...@example.com', user_view.display_name)
      # Assert profile url still contains user ID.
      self.assertEqual('/u/%s/' % viewed_user_id, user_view.profile_url)

  def testRevealEmailsToPriviledgedDomain(self):
    for priviledged_user_domain in settings.priviledged_user_domains:
      self.mr.auth.user_pb.email = 'test@' + priviledged_user_domain
      self.CheckRevealAllToMember(100001L, True)

  def testRevealEmailToSelf(self):
    self.mr.auth.user_pb.email = 'user@example.com'
    self.CheckRevealAllToMember(100001L, True)

  def testRevealAllEmailsToMembers_Collaborators(self):
    self.CheckRevealAllToMember(0L, False)
    self.CheckRevealAllToMember(111L, True)
    self.CheckRevealAllToMember(222L, True)
    self.CheckRevealAllToMember(333L, True)
    self.CheckRevealAllToMember(444L, False)

    # Viewed user has indirect role in the project via a group.
    self.CheckRevealAllToMember(0, False, group_id=888L)
    self.CheckRevealAllToMember(111L, True, group_id=888L)
    # xxx re-implement
    # self.CheckRevealAllToMember(
    #     111, True, viewed_user_id=444L, group_id=888L)

    # Logged in user has indirect role in the project via a group.
    self.CheckRevealAllToMember(888L, True)

  def testRevealAllEmailsToMembers_Admins(self):
    self.CheckRevealAllToMember(555L, False)
    self.mr.auth.user_pb.is_site_admin = True
    self.CheckRevealAllToMember(555L, True)


class RevealAllEmailsTest(unittest.TestCase):

  def testRevealAllEmail(self):
    users_by_id = {
        111L: framework_views.UserView(111L, 'a@a.com', True),
        222L: framework_views.UserView(222L, 'b@b.com', True),
        333L: framework_views.UserView(333L, 'c@c.com', True),
        999L: framework_views.UserView(999L, 'z@z.com', True),
        }
    # Assert display names are obscured before the reveal.
    self.assertEqual('a...@a.com', users_by_id[111L].display_name)
    self.assertEqual('b...@b.com', users_by_id[222L].display_name)
    self.assertEqual('c...@c.com', users_by_id[333L].display_name)
    self.assertEqual('z...@z.com', users_by_id[999L].display_name)

    framework_views.RevealAllEmails(users_by_id)

    self.assertFalse(users_by_id[111L].obscure_email)
    self.assertFalse(users_by_id[222L].obscure_email)
    self.assertFalse(users_by_id[333L].obscure_email)
    self.assertFalse(users_by_id[999L].obscure_email)
    # Assert display names are now revealed.
    self.assertEqual('a@a.com', users_by_id[111L].display_name)
    self.assertEqual('b@b.com', users_by_id[222L].display_name)
    self.assertEqual('c@c.com', users_by_id[333L].display_name)
    self.assertEqual('z@z.com', users_by_id[999L].display_name)
