# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from findit_v2.model.gitiles_commit import Culprit
from waterfall.test import wf_testcase


class CulpritTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(CulpritTest, self).setUp()
    self.gitiles_host = 'chromium.googlesource.com'
    self.gitiles_project = 'chromium/src'
    self.gitiles_ref = 'refs/heads/master'

  def testGetCulprit(self):
    gitiles_id = 'git_hash'
    Culprit.Create(self.gitiles_host, self.gitiles_project, self.gitiles_ref,
                   gitiles_id, 65432).put()

    culprit = Culprit.GetOrCreate(self.gitiles_host, self.gitiles_project,
                                  self.gitiles_ref, gitiles_id)

    self.assertIsNotNone(culprit)
    self.assertEqual([], culprit.failure_urlsafe_keys)

  def testCreateCulprit(self):
    gitiles_id = '67890'
    culprit = Culprit.GetOrCreate(
        self.gitiles_host,
        self.gitiles_project,
        self.gitiles_ref,
        gitiles_id,
        commit_position=67890,
        failure_urlsafe_keys=['failure_urlsafe_key'])

    self.assertIsNotNone(culprit)
    self.assertEqual(['failure_urlsafe_key'], culprit.failure_urlsafe_keys)
