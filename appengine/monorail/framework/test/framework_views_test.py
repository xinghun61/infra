# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for framework_views classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import unittest

from framework import framework_constants
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


class UserViewTest(unittest.TestCase):

  def setUp(self):
    self.user = user_pb2.User(user_id=111)

  def testGetAvailablity_Anon(self):
    self.user.user_id = 0
    user_view = framework_views.UserView(self.user)
    self.assertEquals(None, user_view.avail_message)
    self.assertEquals(None, user_view.avail_state)

  def testGetAvailablity_Banned(self):
    self.user.banned = 'spamming'
    user_view = framework_views.UserView(self.user)
    self.assertEquals('Banned', user_view.avail_message)
    self.assertEquals('banned', user_view.avail_state)

  def testGetAvailablity_Vacation(self):
    self.user.vacation_message = 'gone fishing'
    user_view = framework_views.UserView(self.user)
    self.assertEquals('gone fishing', user_view.avail_message)
    self.assertEquals('none', user_view.avail_state)

    self.user.vacation_message = (
      'Gone fishing as really long time with lots of friends and reading '
      'a long novel by a famous author.  I wont have internet access but '
      'If you urgently need anything you can call Alice or Bob for most '
      'things otherwise call Charlie.  Wish me luck! ')
    user_view = framework_views.UserView(self.user)
    self.assertTrue(len(user_view.avail_message) >= 50)
    self.assertTrue(len(user_view.avail_message_short) < 50)
    self.assertEquals('none', user_view.avail_state)

  def testGetAvailablity_Bouncing(self):
    self.user.email_bounce_timestamp = 1234567890
    user_view = framework_views.UserView(self.user)
    self.assertEquals('Email to this user bounced', user_view.avail_message)
    self.assertEquals(user_view.avail_message_short, user_view.avail_message)
    self.assertEquals('none', user_view.avail_state)

  def testGetAvailablity_Groups(self):
    user_view = framework_views.UserView(self.user, is_group=True)
    self.assertEquals(None, user_view.avail_message)
    self.assertEquals(None, user_view.avail_state)

    self.user.email = 'likely-user-group@example.com'
    user_view = framework_views.UserView(self.user)
    self.assertEquals(None, user_view.avail_message)
    self.assertEquals(None, user_view.avail_state)

  def testGetAvailablity_NeverVisitied(self):
    self.user.last_visit_timestamp = 0
    user_view = framework_views.UserView(self.user)
    self.assertEquals('User never visited', user_view.avail_message)
    self.assertEquals('never', user_view.avail_state)

  def testGetAvailablity_NotRecent(self):
    now = int(time.time())
    self.user.last_visit_timestamp = now - 20 * framework_constants.SECS_PER_DAY
    user_view = framework_views.UserView(self.user)
    self.assertEquals('Last visit 20 days ago', user_view.avail_message)
    self.assertEquals('unsure', user_view.avail_state)

  def testGetAvailablity_ReallyLongTime(self):
    now = int(time.time())
    self.user.last_visit_timestamp = now - 99 * framework_constants.SECS_PER_DAY
    user_view = framework_views.UserView(self.user)
    self.assertEquals('Last visit > 30 days ago', user_view.avail_message)
    self.assertEquals('none', user_view.avail_state)

  def testDeletedUser(self):
    deleted_user = user_pb2.User(user_id=1)
    user_view = framework_views.UserView(deleted_user)
    self.assertEqual(
        user_view.display_name, framework_constants.DELETED_USER_NAME)
    self.assertEqual(user_view.email, '')
    self.assertEqual(user_view.obscure_email, '')
    self.assertEqual(user_view.profile_url, '')

class RevealEmailsToMembersTest(unittest.TestCase):

  def setUp(self):
    project = project_pb2.Project()
    project.owner_ids.append(111)
    project.committer_ids.append(222)
    project.contributor_ids.append(333)
    project.contributor_ids.append(888)
    user = user_pb2.User()
    user.is_site_admin = False
    self.mr = monorailrequest.MonorailRequest(None)
    self.mr.project = project
    self.mr.auth.user_pb = user

  def CheckRevealAllToMember(
      self, logged_in_user_id, expected, viewed_user_id=333, group_id=None):
    user_view = framework_views.StuffUserView(
        viewed_user_id, 'user@example.com', True)

    if group_id:
      pass  # xxx re-implement groups

    users_by_id = {333: user_view}
    self.mr.auth.user_id = logged_in_user_id
    self.mr.auth.effective_ids = {logged_in_user_id}
    # Assert display name is obscured before the reveal.
    self.assertEqual('u...@example.com', user_view.display_name)
    # Assert profile url contains user ID before the reveal.
    self.assertEqual('/u/%s/' % viewed_user_id, user_view.profile_url)
    framework_views.RevealAllEmailsToMembers(
        self.mr.auth, self.mr.project, users_by_id)
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

  def testDontRevealEmailsToPriviledgedDomain(self):
    """We no longer give this advantage based on email address domain."""
    for priviledged_user_domain in settings.priviledged_user_domains:
      self.mr.auth.user_pb.email = 'test@' + priviledged_user_domain
      self.CheckRevealAllToMember(100001, False)

  def testRevealEmailToSelf(self):
    self.mr.auth.user_pb.email = 'user@example.com'
    self.CheckRevealAllToMember(100001, True)

  def testRevealAllEmailsToMembers_Collaborators(self):
    self.CheckRevealAllToMember(0, False)
    self.CheckRevealAllToMember(111, True)
    self.CheckRevealAllToMember(222, True)
    self.CheckRevealAllToMember(333, True)
    self.CheckRevealAllToMember(444, False)

    # Viewed user has indirect role in the project via a group.
    self.CheckRevealAllToMember(0, False, group_id=888)
    self.CheckRevealAllToMember(111, True, group_id=888)
    # xxx re-implement
    # self.CheckRevealAllToMember(
    #     111, True, viewed_user_id=444, group_id=888)

    # Logged in user has indirect role in the project via a group.
    self.CheckRevealAllToMember(888, True)

  def testRevealAllEmailsToMembers_Admins(self):
    self.CheckRevealAllToMember(555, False)
    self.mr.auth.user_pb.is_site_admin = True
    self.CheckRevealAllToMember(555, True)


class RevealAllEmailsTest(unittest.TestCase):

  def testRevealAllEmail(self):
    users_by_id = {
        111: framework_views.StuffUserView(111, 'a@a.com', True),
        222: framework_views.StuffUserView(222, 'b@b.com', True),
        333: framework_views.StuffUserView(333, 'c@c.com', True),
        999: framework_views.StuffUserView(999, 'z@z.com', True),
        }
    # Assert display names are obscured before the reveal.
    self.assertEqual('a...@a.com', users_by_id[111].display_name)
    self.assertEqual('b...@b.com', users_by_id[222].display_name)
    self.assertEqual('c...@c.com', users_by_id[333].display_name)
    self.assertEqual('z...@z.com', users_by_id[999].display_name)

    framework_views.RevealAllEmails(users_by_id)

    self.assertFalse(users_by_id[111].obscure_email)
    self.assertFalse(users_by_id[222].obscure_email)
    self.assertFalse(users_by_id[333].obscure_email)
    self.assertFalse(users_by_id[999].obscure_email)
    # Assert display names are now revealed.
    self.assertEqual('a@a.com', users_by_id[111].display_name)
    self.assertEqual('b@b.com', users_by_id[222].display_name)
    self.assertEqual('c@c.com', users_by_id[333].display_name)
    self.assertEqual('z@z.com', users_by_id[999].display_name)
