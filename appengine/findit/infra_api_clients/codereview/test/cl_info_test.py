# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from infra_api_clients.codereview import cl_info


class ClInfoTest(unittest.TestCase):

  server = 'codereview.chromium.org'
  change_id = '20002000'
  patchset_id = '2000'
  revision = 'abcd'
  timestamp = datetime.datetime(2017, 1, 2, 3, 4, 5)
  formatted_ts = '2017-01-02 03:04:05 UTC'
  email = 'developer@test.com'

  def testCommit(self):
    commit = cl_info.Commit(self.patchset_id, self.revision, self.timestamp)
    self.assertEqual({
        'patchset_id': self.patchset_id,
        'revision': self.revision,
        'timestamp': self.formatted_ts
    }, commit.serialize())

  def testCommitAttempt(self):
    commit_attempt = cl_info.CommitAttempt(self.patchset_id, self.email,
                                           self.timestamp)
    self.assertEqual({
        'patchset_id': self.patchset_id,
        'committing_user_email': self.email,
        'timestamp': self.formatted_ts
    }, commit_attempt.serialize())

  def testRevertWithNoCl(self):
    revert = cl_info.Revert(self.patchset_id, None, self.email, self.timestamp)
    self.assertEqual({
        'patchset_id': self.patchset_id,
        'reverting_user_email': self.email,
        'timestamp': self.formatted_ts
    }, revert.serialize())

  def testRevertWithBareCl(self):
    cl = cl_info.ClInfo(self.server, self.change_id)
    revert = cl_info.Revert(self.patchset_id, cl, self.email, self.timestamp)
    self.assertEqual({
        'patchset_id': self.patchset_id,
        'reverting_user_email': self.email,
        'timestamp': self.formatted_ts,
        'reverting_cl': {
            'auto_revert_off': False,
            'cc': [],
            'change_id': '20002000',
            'closed': None,
            'commit_attempts': [],
            'commits': [],
            'description': None,
            'owner_email': None,
            'reverts': [],
            'reviewers': [],
            'server_hostname': 'codereview.chromium.org',
            'subject': None
        }
    }, revert.serialize())

  def testClInfo(self):

    def hours(h):
      return datetime.timedelta(hours=h)

    cl = cl_info.ClInfo(self.server, self.change_id)
    # Adding two attempts with the same timestamp to cover the codepath that
    # checks that the timestamp is different.
    cl.AddCqAttempt(self.patchset_id, self.email, self.timestamp)
    cl.AddCqAttempt(self.patchset_id, self.email, self.timestamp)
    cl.AddCqAttempt(
        self.patchset_id,
        self.email,
        self.timestamp + datetime.timedelta(hours=1))

    cl.commits.append(
        cl_info.Commit(self.patchset_id, self.revision, self.timestamp +
                       hours(1)))
    self.assertEqual(self.patchset_id,
                     cl.GetPatchsetIdByRevision(self.revision))

    cl.commits.append(
        cl_info.Commit('3000', 'ef1234', self.timestamp + hours(2)))
    self.assertEqual('3000', cl.GetPatchsetIdByRevision('ef1234'))
    self.assertIsNone(cl.GetPatchsetIdByRevision('deadc0de'))

    revert_cl_1 = cl_info.ClInfo(self.server, 'revert1')
    revert_cl_1.commits.append(
        cl_info.Commit('r1p1', '007c0de', self.timestamp + hours(3)))
    revert1 = cl_info.Revert(self.patchset_id, revert_cl_1, 'reverter@test.com',
                             self.timestamp + hours(3))
    cl.reverts.append(revert1)
    self.assertEqual('007c0de',
                     cl.GetRevertCLsByRevision(self.revision)[0]
                     .reverting_cl.commits[0].revision)
    self.assertEqual([], cl.GetRevertCLsByRevision('ef1234'))
    self.assertIsNone(cl.GetRevertCLsByRevision('deadc0de'))
