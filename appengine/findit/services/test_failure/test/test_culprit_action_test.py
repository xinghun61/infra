# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common.waterfall import failure_type
from dto.dict_of_basestring import DictOfBasestring
from libs import time_util
from libs.list_of_basestring import ListOfBasestring
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from services.parameters import BuildKey
from services.parameters import CulpritActionParameters
from services.parameters import FailureToCulpritMap
from services.test_failure import test_culprit_action
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class TestCulpritActionTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(TestCulpritActionTest, self).setUp()

    repo_name = 'chromium'
    revision = 'rev1'

    self.culprit = WfSuspectedCL.Create(repo_name, revision,
                                        100).put().urlsafe()

    culprit_dict = DictOfBasestring()
    culprit_dict[revision] = self.culprit

    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(self.culprit)

    parameters_dict = {
        'build_key': {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 123
        },
        'culprits': {
            'rev1': self.culprit
        },
        'heuristic_cls': heuristic_cls
    }
    self.parameters = CulpritActionParameters.FromSerializable(parameters_dict)

  def testCulpritIsNotSuspect(self):
    parameters_dict = {
        'build_key': {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 123
        },
        'culprits': {
            'rev1': {
                'repo_name': 'chromium',
                'revision': 'rev1'
            }
        },
        'heuristic_cls': []
    }
    parameters = CulpritActionParameters.FromSerializable(parameters_dict)
    self.assertFalse(
        test_culprit_action.CanAutoCreateRevert(self.culprit, parameters))

  @mock.patch.object(waterfall_config, 'GetActionSettings', return_value={})
  def testRevertTurnedOff(self, _):
    self.assertFalse(
        test_culprit_action.CanAutoCreateRevert(self.culprit, self.parameters))

  @mock.patch.object(
      test_culprit_action, '_GetDailyNumberOfRevertedCulprits', return_value=10)
  def testAutoRevertExceedsLimit(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    self.assertFalse(
        test_culprit_action.CanAutoCreateRevert(self.culprit, self.parameters))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 2, 14, 16, 0, 0))
  def testCanAutoCreateRevert(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.failure_type.append(failure_type.TEST)
    culprit.revert_created_time = datetime(2018, 2, 14, 12, 0, 0)
    culprit.put()

    culprit_dict = DictOfBasestring()
    culprit_dict[revision] = culprit.key.urlsafe()

    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(culprit.key.urlsafe())

    parameters_dict = {
        'build_key': {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 123
        },
        'culprits': {
            'rev1': culprit.key.urlsafe()
        },
        'heuristic_cls': heuristic_cls
    }

    parameters = CulpritActionParameters.FromSerializable(parameters_dict)

    self.assertTrue(
        test_culprit_action.CanAutoCreateRevert(culprit.key.urlsafe(),
                                                parameters))

  @mock.patch.object(
      waterfall_config,
      'GetActionSettings',
      return_value={'auto_commit_revert_test': False})
  def testCanNotCommitRevertFeatureIsOff(self, _):
    self.assertFalse(test_culprit_action.CanAutoCommitRevertByFindit())

  @mock.patch.object(
      test_culprit_action, '_GetDailyNumberOfCommits', return_value=10)
  def testCannotCommitRevertFeatureCommitExceeds(self, _):
    self.assertFalse(test_culprit_action.CanAutoCommitRevertByFindit())

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 2, 14, 16, 0, 0))
  def testCanAutoCommitRevertByFindit(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.failure_type.append(failure_type.TEST)
    culprit.revert_committed_time = datetime(2018, 2, 14, 12, 0, 0)
    culprit.put()

    self.assertTrue(test_culprit_action.CanAutoCommitRevertByFindit())

  @mock.patch.object(
      ci_failure, 'GetLaterBuildsWithAnySameStepFailure', return_value={})
  def testShouldNotTakeActionsOnCulpritIfBuildGreen(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    culprits = DictOfBasestring()
    culprits['r1'] = 'mockurlsafekey'
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            'test1': 'r1',
            'test2': 'r1'
        },
        'step2': {
            'test1': 'r1'
        }
    })
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfBasestring(),
        failure_to_culprit_map=failure_to_culprit_map)
    self.assertEqual(
        [], test_culprit_action.GetCulpritsShouldTakeActions(parameters))

  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={125: ['step3']})
  def testGetCulpritsShouldTakeActionsNoSameStepFailure(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    culprits = DictOfBasestring()
    culprits['r1'] = 'mockurlsafekey'
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            'test1': 'r1',
            'test2': 'r1'
        },
        'step2': {
            'test1': 'r1'
        }
    })

    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfBasestring(),
        failure_to_culprit_map=failure_to_culprit_map)
    self.assertEquals(
        [], test_culprit_action.GetCulpritsShouldTakeActions(parameters))

  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={125: ['step1', 'step2']})
  def testGetCulpritsShouldTakeActions(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    culprits = DictOfBasestring()
    culprits['r1'] = 'mockurlsafekey'
    failure_to_culprit_map = FailureToCulpritMap.FromSerializable({
        'step1': {
            'test1': 'r1',
            'test2': 'r1'
        },
        'step2': {
            'test1': 'r1'
        }
    })

    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfBasestring(),
        failure_to_culprit_map=failure_to_culprit_map)
    self.assertTrue(
        ['r1'], test_culprit_action.GetCulpritsShouldTakeActions(parameters))
