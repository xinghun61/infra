# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueremovehotlist JSON feed."""

import unittest
import logging

import webapp2

from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueremovehotlist

class RemoveFromHotlist(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        features=fake.FeaturesService())
    services.user.TestAddUser('user_111@domain.com', 111L)
    services.user.TestAddUser('user_222@domain.com', 222L)

    self.project = services.project.TestAddProject('proj')
    self.project.owner_ids.extend([111L])
    self.project.owner_ids.extend([222L])
    self.issue = fake.MakeTestIssue(
        self.project.project_id, 1, 'one', 'New', 111L)
    services.issue.TestAddIssue(self.issue)

    hotlist_item_tuple = (self.issue.issue_id, 11, 111L, 23461443, '')
    services.features.TestAddHotlist(
        'name_111', hotlist_id=111, owner_ids=[111L], editor_ids=[222L],
        hotlist_item_fields=[hotlist_item_tuple])
    services.features.TestAddHotlist(
        'name_222', hotlist_id=222, owner_ids=[111L], editor_ids=[222L],
        hotlist_item_fields=[hotlist_item_tuple])

    self.servlet = issueremovehotlist.RemoveFromHotlist(
        'req', webapp2.Response(), services=services)
    self.services = services

  def testHandleRequest_ExistingHotlist(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.auth.user_id = 222L
    mr.auth.effective_ids = {222L}
    mr.hotlist_ids = [111]
    mr.issue_refs = ['proj: 1']
    json_data = self.servlet.HandleRequest(mr)
    logging.info(json_data)
    self.assertItemsEqual(json_data['updatedHotlistNames'],
                          ['name_111'])
    self.assertItemsEqual(json_data['allHotlistNames'],
                         ['name_222'])
    self.assertItemsEqual(json_data['missed'], [])
