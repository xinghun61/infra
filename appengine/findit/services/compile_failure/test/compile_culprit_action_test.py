# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dto.dict_of_basestring import DictOfBasestring
from libs.list_of_basestring import ListOfBasestring
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from services.compile_failure import compile_culprit_action
from services.parameters import BuildKey
from services.parameters import CulpritActionParameters
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

  @mock.patch.object(
      ci_failure, 'GetLaterBuildsWithAnySameStepFailure', return_value={})
  def testShouldNotTakeActionsOnCulpritIfBuildGreen(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    culprits = DictOfBasestring()
    culprits['r1'] = 'mockurlsafekey'
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfBasestring())
    self.assertFalse(
        compile_culprit_action.ShouldTakeActionsOnCulprit(parameters))

  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={125: ['compile']})
  def testShouldTakeActionsOnCulprit(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    culprits = DictOfBasestring()
    culprits['r1'] = 'mockurlsafekey'
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfBasestring())
    self.assertTrue(
        compile_culprit_action.ShouldTakeActionsOnCulprit(parameters))
