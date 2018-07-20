# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.wf_suspected_cl import WfSuspectedCL
from services.compile_failure import compile_culprit_action
from services import git
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CompileCulpritActionTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(waterfall_config, 'GetActionSettings', return_value={})
  def testRevertTurnedOff(self, _):
    self.assertFalse(compile_culprit_action.CanAutoCreateRevert())

  @mock.patch.object(
      compile_culprit_action,
      '_GetDailyNumberOfRevertedCulprits',
      return_value=10)
  def testAutoRevertExceedsLimit(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    self.assertFalse(compile_culprit_action.CanAutoCreateRevert())

  def testCanAutoCreateRevert(self):
    self.assertTrue(compile_culprit_action.CanAutoCreateRevert())

  @mock.patch.object(
      waterfall_config,
      'GetActionSettings',
      return_value={'auto_commit_revert_compile': False})
  def testCanNotCommitRevertFeatureIsOff(self, _):
    self.assertFalse(compile_culprit_action.CanAutoCommitRevertByFindit())

  @mock.patch.object(
      compile_culprit_action, '_GetDailyNumberOfCommits', return_value=10)
  def testCannotCommitRevertFeatureCommitExceeds(self, _):
    self.assertFalse(compile_culprit_action.CanAutoCommitRevertByFindit())

  def testCanAutoCommitRevertByFindit(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    self.assertTrue(compile_culprit_action.CanAutoCommitRevertByFindit())
