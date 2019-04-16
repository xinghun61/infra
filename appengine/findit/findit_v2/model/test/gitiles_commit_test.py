# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from findit_v2.model.gitiles_commit import Culprit
from waterfall.test import wf_testcase


class CulpritTest(wf_testcase.WaterfallTestCase):

  def testCreateCulprit(self):
    gitiles_host = 'chromium.googlesource.com'
    gitiles_project = 'chromium/src'
    gitiles_ref = 'refs/heads/master'
    gitiles_id = 'git_hash'
    Culprit.Create(gitiles_host, gitiles_project, gitiles_ref, gitiles_id,
                   65432).put()

    culprit = Culprit.Get(gitiles_host, gitiles_project, gitiles_ref,
                          gitiles_id)

    self.assertIsNotNone(culprit)
    self.assertEqual([], culprit.failure_urlsafe_keys)
