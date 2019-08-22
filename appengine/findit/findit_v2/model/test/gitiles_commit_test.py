# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from findit_v2.model.gitiles_commit import Culprit
from findit_v2.model.gitiles_commit import Suspect
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


class SuspectTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SuspectTest, self).setUp()
    self.gitiles_host = 'chromium.googlesource.com'
    self.gitiles_project = 'chromium/src'
    self.gitiles_ref = 'refs/heads/master'

  def testCreateSuspect(self):
    gitiles_id = '67890'
    Suspect.GetOrCreate(
        self.gitiles_host,
        self.gitiles_project,
        self.gitiles_ref,
        gitiles_id,
        commit_position=67890,
        hints={'add a/b/c.cc': 5})
    suspect_reloaded = Suspect.GetOrCreate(
        self.gitiles_host, self.gitiles_project, self.gitiles_ref, gitiles_id)
    self.assertEqual('add a/b/c.cc', suspect_reloaded.hints[0].content)
    self.assertEqual(5, suspect_reloaded.hints[0].score)
    self.assertEqual(67890, suspect_reloaded.commit_position)

  def testReCreateSuspect(self):
    gitiles_id = '600dc0de'
    Suspect.GetOrCreate(
        self.gitiles_host,
        self.gitiles_project,
        self.gitiles_ref,
        gitiles_id,
        commit_position=67891,
        hints={'add a/b/c.cc': 5})
    # If GetOrCreate is called again with new hints, these should be added.
    suspect_reloaded = Suspect.GetOrCreate(
        self.gitiles_host,
        self.gitiles_project,
        self.gitiles_ref,
        gitiles_id,
        hints={'delete a/b/d.cc': 5})
    self.assertEqual('add a/b/c.cc', suspect_reloaded.hints[0].content)
    self.assertEqual(5, suspect_reloaded.hints[0].score)
    self.assertEqual('delete a/b/d.cc', suspect_reloaded.hints[1].content)
    self.assertEqual(5, suspect_reloaded.hints[1].score)
    self.assertEqual(67891, suspect_reloaded.commit_position)
