# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the issueupdatehotlsits JSON feed."""

import unittest
import logging

import webapp2

from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issueupdatehotlists

class UpdateHotlists(unittest.TestCase):

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
    services.features.TestAddHotlist(
        'name_444', hotlist_id=444, owner_ids=[111L], editor_ids=[222L],
        hotlist_item_fields=[(self.issue.issue_id, 1, 111L, 23461444, '')])

    self.servlet = issueupdatehotlists.UpdateHotlists(
        'req', webapp2.Response(), services=services)
    self.services = services

  def testHandleRequest_AddRemoveIssues(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.auth.user_id = 222L
    mr.auth.effective_ids = {222L}
    mr.hotlist_ids_remove = [333, 444]
    mr.hotlist_ids_add = [111, 222]
    mr.issue_refs = ['proj: 1']
    json_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(
        json_data['updatedHotlistNames'],
        ['name_111', 'name_222', 'name_333', 'name_444'])

    self.assertItemsEqual(json_data['issueHotlistNames'],
                          ['name_111', 'name_222'])
    self.assertEqual(len(json_data['issueHotlistIds']), 2)
    self.assertEqual(len(json_data['issueHotlistUrls']), 2)

    self.assertItemsEqual(json_data['remainingHotlistIds'], [333, 444])
    self.assertEqual(len(json_data['remainingHotlistNames']), 2)

    self.assertItemsEqual(json_data['missed'], [])

  def testHandleRequest_NewHotlist(self):
    mr = testing_helpers.MakeMonorailRequest(project=self.project)
    mr.auth.user_id = 222L
    mr.auth.effective_ids = {222L}
    mr.issue_refs = ['proj: 1']
    json_data = self.servlet.HandleRequest(mr)
    self.assertItemsEqual(
        json_data['updatedHotlistNames'], ['Hotlist-1'])

    self.assertItemsEqual(json_data['issueHotlistNames'],
                          ['name_333', 'name_444', 'Hotlist-1'])
    self.assertEqual(len(json_data['issueHotlistIds']), 3)
    self.assertEqual(len(json_data['issueHotlistUrls']), 3)

    self.assertItemsEqual(json_data['remainingHotlistIds'], [111, 222])
    self.assertEqual(len(json_data['remainingHotlistNames']), 2)

    self.assertItemsEqual(json_data['missed'], [])
