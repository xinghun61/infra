# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueaddtohotlist JSON feed."""

import unittest
import logging

import webapp2

from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueaddtohotlist

class AddToHotlistTest(unittest.TestCase):

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

    services.features.TestAddHotlist(
        'name_111', hotlist_id=111, owner_ids=[111L], editor_ids=[222L])
    services.features.TestAddHotlist(
        'name_222', hotlist_id=222, owner_ids=[111L], editor_ids=[222L])
    services.features.TestAddHotlist(
        'name_333', hotlist_id=333,  owner_ids=[222L], editor_ids=[111L],
        hotlist_item_fields=[(self.issue.issue_id, 1, 111L, 23461443, '')])

    self.servlet = issueaddtohotlist.AddToHotlist(
        'req', webapp2.Response(), services=services)
    self.services = services

  def testHandleRequest_ExistingHotlist(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.auth.user_id = 222L
    mr.auth.effective_ids = {222L}
    mr.hotlist_ids = [111, 222]
    mr.issue_refs = ['proj: 1']
    json_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(json_data['updatedHotlistNames'],
                          ['name_111', 'name_222'])
    self.assertItemsEqual(json_data['allHotlistNames'],
                         ['name_111', 'name_222', 'name_333'])
    self.assertItemsEqual(json_data['missed'], [])

  def testHandleRequest_NewHotlist(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.auth.user_id = 222L
    mr.auth.effective_ids = {222L}
    mr.issue_refs = ['proj: 1']
    json_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(json_data['updatedHotlistNames'], ['Hotlist-1'])
    self.assertItemsEqual(json_data['allHotlistNames'],
                         ['Hotlist-1', 'name_333'])
    self.assertItemsEqual(json_data['missed'], [])
