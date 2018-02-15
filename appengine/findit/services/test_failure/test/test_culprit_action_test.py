# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common.waterfall import failure_type
from libs import time_util
from model.wf_suspected_cl import WfSuspectedCL
from services import gerrit
from services.parameters import CLKey
from services.parameters import CulpritActionParameters
from services.test_failure import test_culprit_action
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class TestCulpritActionTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(TestCulpritActionTest, self).setUp()
    culprit_dict = {'repo_name': 'chromium', 'revision': 'rev1'}
    self.culprit = CLKey.FromSerializable(culprit_dict)

    parameters_dict = {
        'build_key': {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 123
        },
        'culprits': {
            'rev1': culprit_dict
        },
        'heuristic_cls': [culprit_dict]
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
    culprit = WfSuspectedCL.Create('chromium', 'rev1', 123)
    culprit.failure_type.append(failure_type.TEST)
    culprit.revert_created_time = datetime(2018, 2, 14, 12, 0, 0)
    culprit.put()
    self.assertTrue(
        test_culprit_action.CanAutoCreateRevert(self.culprit, self.parameters))

  @mock.patch.object(
      waterfall_config,
      'GetActionSettings',
      return_value={
          'auto_commit_revert_test': False
      })
  def testCanNotCommitRevertFeatureIsOff(self, _):
    self.assertFalse(
        test_culprit_action.CanAutoCommitRevertByFindit(
            gerrit.CREATED_BY_FINDIT))

  @mock.patch.object(
      test_culprit_action, '_GetDailyNumberOfCommits', return_value=10)
  def testCannotCommitRevertFeatureCommitExceeds(self, _):
    self.assertFalse(
        test_culprit_action.CanAutoCommitRevertByFindit(
            gerrit.CREATED_BY_FINDIT))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 2, 14, 16, 0, 0))
  @mock.patch.object(suspected_cl_util, 'GetCulpritInfo')
  def testCanAutoCommitRevertByFindit(self, mock_info, _):
    repo_name = 'chromium'
    revision = 'rev1'

    mock_info.return_value = {
        'commit_position': 123,
        'code_review_url': 'https://chromium-review.googlesource.com/12345',
        'review_server_host': 'chromium-review.googlesource.com',
        'review_change_id': '12345',
        'author': {
            'email': 'abc@chromium.org'
        }
    }
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.failure_type.append(failure_type.TEST)
    culprit.revert_committed_time = datetime(2018, 2, 14, 12, 0, 0)
    culprit.put()

    self.assertTrue(
        test_culprit_action.CanAutoCommitRevertByFindit(
            gerrit.CREATED_BY_FINDIT))
