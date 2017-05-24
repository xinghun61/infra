# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.tracker.issuererank."""

import logging
import mox
import unittest

from framework import monorailrequest
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issuererank
from tracker import tracker_bizobj
from tracker import tracker_helpers


class IssueRerankTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue_star=fake.IssueStarService(),
        spam=fake.SpamService())
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.servlet = issuererank.IssueRerank(
        'req', 'res', self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testHandleRequest_NoChange(self):
    mr, _ = self.SetUpHandleRequest()
    self.mox.ReplayAll()
    ret = self.servlet.HandleRequest(mr)
    self.mox.VerifyAll()
    self.assertDictContainsSubset(
        {'summary': 'summary0', 'issue_id': 78900, 'issue_ref': 120,
         'is_open': 'yes'}, ret['issues'][0])
    self.assertDictContainsSubset(
        {'summary': 'summary1', 'issue_id': 78901, 'issue_ref': 121,
         'is_open': 'yes'}, ret['issues'][1])

  def testHandleRequest_OneMoved(self):
    mr, issue = self.SetUpHandleRequest(3, 78900, [78902], True)
    self.SetUpRerankIssues(issue, 78900, [78902], True)

    self.mox.StubOutWithMock(self.services.issue, 'ApplyIssueRerank')
    self.mox.StubOutWithMock(self.services.issue, 'GetIssue')

    self.services.issue.ApplyIssueRerank(mr.cnxn, issue.issue_id, [(78902, 5)])
    issue.blocked_on_iids = [78900, 78902, 78901]
    issue.blocked_on_ranks = [0, 5, 10]
    self.services.issue.GetIssue(mr.cnxn, issue.issue_id).AndReturn(issue)
    self.mox.ReplayAll()
    ret = self.servlet.HandleRequest(mr)
    self.assertDictContainsSubset(
        {'summary': 'summary0', 'issue_id': 78900, 'issue_ref': 120,
         'is_open': 'yes'}, ret['issues'][0])
    self.assertDictContainsSubset(
        {'summary': 'summary2', 'issue_id': 78902, 'issue_ref': 122,
         'is_open': 'yes'}, ret['issues'][1])
    self.assertDictContainsSubset(
        {'summary': 'summary1', 'issue_id': 78901, 'issue_ref': 121,
         'is_open': 'yes'}, ret['issues'][2])
    self.mox.VerifyAll()

  def testHandleRequest_NoIssue(self):
    mr = testing_helpers.MakeMonorailRequest()
    self.assertRaises(
        monorailrequest.InputException, self.servlet.HandleRequest, mr)

  def SetUpHandleRequest(
      self, blocked_count=2, target_id=None, moved_ids=None, split_above=None):
    mr = testing_helpers.MakeMonorailRequest()
    mr.parent_id = 78899
    mr.target_id = target_id
    mr.moved_ids = moved_ids
    mr.split_above = split_above
    issue = fake.MakeTestIssue(987, 119, 'summary', 'New', 111L,
        issue_id=78899)
    blocked_on_issues = {}
    for i in xrange(blocked_count):
      issue_id = 78900 + i
      blocked_on_issues[issue_id] = fake.MakeTestIssue(
          987, 120 + i, 'summary%d' % i, 'New', 111L, issue_id=issue_id)
      issue.blocked_on_iids.append(issue_id)
      issue.blocked_on_ranks.append(10 * i)

    self.mox.StubOutWithMock(tracker_helpers,
        'GetAllowedOpenAndClosedRelatedIssues')
    self.mox.StubOutWithMock(self.services.issue, 'GetIssuesDict')

    all_ids = [78899]
    if target_id and moved_ids:
      all_ids.extend([target_id] + moved_ids)
    ret = {78899: issue}
    ret.update({(78900 + i): blocked_on_issues[issue_id]
               for i in xrange(blocked_count)})
    self.services.issue.GetIssuesDict(mr.cnxn, all_ids).AndReturn(ret)
    tracker_helpers.GetAllowedOpenAndClosedRelatedIssues(
        self.services, mr, issue).AndReturn(
            (blocked_on_issues, {}))
    self.services.issue.GetIssuesDict(
        mr.cnxn, mox.SameElementsAs(blocked_on_issues.keys())).AndReturn(
        blocked_on_issues)
    return mr, issue

  def SetUpRerankIssues(self, issue, target_id, moved_ids, split_above):
    self.mox.StubOutWithMock(tracker_bizobj, 'SplitBlockedOnRanks')

    blocked_and_ranks = zip(issue.blocked_on_iids, issue.blocked_on_ranks)
    open_and_ranks = [x for x in blocked_and_ranks if x[0] not in moved_ids]
    open_ids = [issue_id for issue_id, _ in open_and_ranks]
    target_index = open_ids.index(target_id)
    offset = int(split_above)

    tracker_bizobj.SplitBlockedOnRanks(
        issue, target_id, split_above, open_ids).AndReturn(
            (open_and_ranks[:target_index + offset],
             open_and_ranks[target_index + offset:]))
