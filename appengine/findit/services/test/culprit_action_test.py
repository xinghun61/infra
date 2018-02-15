# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import monitoring
from common.waterfall import failure_type
from libs import analysis_status
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from services import culprit_action
from services import gerrit
from services import irc
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SendNotificationToIrcParameters
from services.parameters import SubmitRevertCLParameters
from waterfall.test import wf_testcase


class CulpritActionTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=True)
  def testShouldNotTakeActionsOnCulpritIfBuildGreen(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    cl_key = CLKey(repo_name='chromium', revision='r1')
    culprits = DictOfCLKeys()
    culprits['r1'] = cl_key
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfCLKeys())
    self.assertFalse(culprit_action.ShouldTakeActionsOnCulprit(parameters))

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=False)
  def testShouldTakeActionsOnCulprit(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    cl_key = CLKey(repo_name='chromium', revision='r1')
    culprits = DictOfCLKeys()
    culprits['r1'] = cl_key
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfCLKeys())
    self.assertTrue(culprit_action.ShouldTakeActionsOnCulprit(parameters))

  def testShouldForceNotify(self):
    culprit_dict = {'repo_name': 'chromium', 'revision': 'rev1'}
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
    self.assertTrue(
        culprit_action.ShouldForceNotify(
            CLKey.FromSerializable(culprit_dict),
            CulpritActionParameters.FromSerializable(parameters_dict)))

  def testRevertHasCompleted(self):
    repo_name = 'chromium'
    revision = 'rev1'
    parameters = CreateRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        build_id='build_id')
    pipeline_id = 'pipeline_id'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = analysis_status.COMPLETED
    culprit.put()

    self.assertFalse(
        culprit_action._CanCreateRevertForCulprit(parameters, pipeline_id))

  def testRevertACulpritIsBeingReverted(self):
    repo_name = 'chromium'
    revision = 'rev1'
    parameters = CreateRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        build_id='build_id')
    pipeline_id = 'another_pipeline'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_status = analysis_status.RUNNING
    culprit.revert_pipeline_id = 'pipeline_id'
    culprit.put()

    self.assertFalse(
        culprit_action._CanCreateRevertForCulprit(parameters, pipeline_id))

  def test_CanCreateRevertForCulprit(self):
    repo_name = 'chromium'
    revision = 'rev1'
    parameters = CreateRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        build_id='build_id')
    pipeline_id = 'pipeline_id'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_status = analysis_status.RUNNING
    culprit.put()

    self.assertTrue(
        culprit_action._CanCreateRevertForCulprit(parameters, pipeline_id))

  def testCanCommitRevert(self):
    repo_name = 'chromium'
    revision = 'rev1'
    parameters = SubmitRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision), revert_status=1)
    pipeline_id = 'pipeline_id'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = analysis_status.COMPLETED
    culprit.put()

    self.assertTrue(culprit_action._CanCommitRevert(parameters, pipeline_id))

  def testCannotCommitRevertByAnotherAnalysis(self):
    repo_name = 'chromium'
    revision = 'rev1'
    parameters = SubmitRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision), revert_status=1)
    pipeline_id = 'another_pipeline'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = analysis_status.COMPLETED
    culprit.revert_submission_status = analysis_status.RUNNING
    culprit.submit_revert_pipeline_id = 'pipeline_id'
    culprit.put()

    self.assertFalse(culprit_action._CanCommitRevert(parameters, pipeline_id))

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionCreated(self, mock_mo):
    culprit_action.MonitorRevertAction(failure_type.COMPILE,
                                       gerrit.CREATED_BY_FINDIT, gerrit.SKIPPED)
    parameters = {'type': 'compile', 'action_taken': 'revert_created'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionConfirmed(self, mock_mo):
    culprit_action.MonitorRevertAction(
        failure_type.COMPILE, gerrit.CREATED_BY_SHERIFF, gerrit.SKIPPED)
    parameters = {'type': 'compile', 'action_taken': 'revert_confirmed'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionSkipped(self, mock_mo):
    culprit_action.MonitorRevertAction(failure_type.COMPILE, gerrit.SKIPPED,
                                       gerrit.SKIPPED)
    self.assertFalse(mock_mo.called)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionError(self, mock_mo):
    culprit_action.MonitorRevertAction(failure_type.COMPILE, gerrit.ERROR,
                                       gerrit.SKIPPED)
    parameters = {'type': 'compile', 'action_taken': 'revert_status_error'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionSubmitted(self, mock_mo):
    culprit_action.MonitorRevertAction(
        failure_type.COMPILE, gerrit.CREATED_BY_FINDIT, gerrit.COMMITTED)
    parameters = {'type': 'compile', 'action_taken': 'revert_committed'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorCommitRevertActionError(self, mock_mo):
    culprit_action.MonitorRevertAction(failure_type.COMPILE,
                                       gerrit.CREATED_BY_FINDIT, gerrit.ERROR)
    parameters = {'type': 'compile', 'action_taken': 'revert_commit_error'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(irc, 'SendMessageToIrc')
  def testNoNeedToSendNotification(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_SHERIFF
    commit_status = gerrit.SKIPPED
    pipeline_input = SendNotificationToIrcParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendMessageToIRC(pipeline_input))
    self.assertFalse(mocked_irc.called)

  @mock.patch.object(irc, 'SendMessageToIrc')
  def testSendNotificationNoCulprit(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    commit_status = gerrit.ERROR
    pipeline_input = SendNotificationToIrcParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendMessageToIRC(pipeline_input))

    self.assertFalse(mocked_irc.called)

  @mock.patch.object(irc, 'SendMessageToIrc')
  def testSendNotificationNoRevert(self, mocked_irc):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    commit_status = gerrit.ERROR

    WfSuspectedCL.Create(repo_name, revision, 1).put()

    pipeline_input = SendNotificationToIrcParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendMessageToIRC(pipeline_input))

    self.assertFalse(mocked_irc.called)

  @mock.patch.object(irc, 'SendMessageToIrc', return_value=True)
  def testSendNotificationToIRC(self, _):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = gerrit.CREATED_BY_FINDIT
    commit_status = gerrit.SKIPPED

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.revert_cl.revert_cl_url = 'revert_url'
    culprit.put()

    pipeline_input = SendNotificationToIrcParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertTrue(culprit_action.SendMessageToIRC(pipeline_input))

  def testShouldNotSendNotificationForSingleFailedBuild(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 1)
    culprit.builds['m/b1/1'] = {}
    culprit.put()

    self.assertFalse(
        culprit_action._ShouldSendNotification('chromium', 'r1', False, None,
                                               2))
    self.assertFalse(culprit.cr_notification_processed)

  def testShouldNotSendNotificationForSameFailedBuild(self):
    culprit = WfSuspectedCL.Create('chromium', 'r2', 1)
    culprit.builds['m/b2/2'] = {}
    culprit.put()
    self.assertTrue(
        culprit_action._ShouldSendNotification('chromium', 'r2', True,
                                               gerrit.CREATED_BY_SHERIFF, 2))
    self.assertFalse(
        culprit_action._ShouldSendNotification('chromium', 'r2', True,
                                               gerrit.CREATED_BY_SHERIFF, 2))
    culprit = WfSuspectedCL.Get('chromium', 'r2')
    self.assertEqual(analysis_status.RUNNING, culprit.cr_notification_status)

  def testShouldSendNotificationForSecondFailedBuild(self):
    culprit = WfSuspectedCL.Create('chromium', 'r3', 1)
    culprit.builds['m/b31/31'] = {}
    culprit.put()
    self.assertFalse(
        culprit_action._ShouldSendNotification('chromium', 'r3', False, None,
                                               2))
    culprit = WfSuspectedCL.Get('chromium', 'r3')
    culprit.builds['m/b32/32'] = {}
    culprit.put()
    self.assertTrue(
        culprit_action._ShouldSendNotification('chromium', 'r3', False, None,
                                               2))
    culprit = WfSuspectedCL.Get('chromium', 'r3')
    self.assertEqual(analysis_status.RUNNING, culprit.cr_notification_status)

  def testShouldNotSendNotificationIfRevertedByFindit(self):
    culprit = WfSuspectedCL.Create('chromium', 'r1', 1)
    culprit.builds['m/b1/1'] = {}
    culprit.put()

    self.assertFalse(
        culprit_action._ShouldSendNotification('chromium', 'r1', True,
                                               gerrit.CREATED_BY_FINDIT, 2))
    self.assertFalse(culprit.cr_notification_processed)

  @mock.patch.object(
      culprit_action, '_ShouldSendNotification', return_value=False)
  def testShouldNotSendNotificationForCulprit(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    force_notify = True
    revert_status = gerrit.CREATED_BY_SHERIFF

    pipeline_input = SendNotificationForCulpritParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        force_notify=force_notify,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendNotificationForCulprit(pipeline_input))

  @mock.patch.object(gerrit, 'SendNotificationForCulprit', return_value=True)
  @mock.patch.object(
      culprit_action, '_ShouldSendNotification', return_value=True)
  def testSendNotification(self, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    force_notify = True
    revert_status = gerrit.CREATED_BY_SHERIFF

    pipeline_input = SendNotificationForCulpritParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        force_notify=force_notify,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    self.assertTrue(culprit_action.SendNotificationForCulprit(pipeline_input))

  @mock.patch.object(
      culprit_action, '_CanCreateRevertForCulprit', return_value=False)
  def testRevertCulpritSkipped(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    pipeline_input = CreateRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        build_id=build_id,
        failure_type=failure_type.COMPILE)
    self.assertEqual(gerrit.SKIPPED,
                     culprit_action.RevertCulprit(pipeline_input,
                                                  'pipeline_id'))

  @mock.patch.object(
      gerrit, 'RevertCulprit', return_value=gerrit.CREATED_BY_FINDIT)
  @mock.patch.object(
      culprit_action, '_CanCreateRevertForCulprit', return_value=True)
  def testRevertCulprit(self, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    pipeline_input = CreateRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        build_id=build_id,
        failure_type=failure_type.COMPILE)
    self.assertEqual(gerrit.CREATED_BY_FINDIT,
                     culprit_action.RevertCulprit(pipeline_input,
                                                  'pipeline_id'))

  @mock.patch.object(culprit_action, '_CanCommitRevert', return_value=False)
  def testCommitSkipped(self, _):
    repo_name = 'chromium'
    revision = 'rev1'

    pipeline_input = SubmitRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=1,
        failure_type=failure_type.COMPILE)

    self.assertEqual(gerrit.SKIPPED,
                     culprit_action.CommitRevert(pipeline_input, 'pipeline_id'))

  @mock.patch.object(gerrit, 'CommitRevert', return_value=gerrit.COMMITTED)
  @mock.patch.object(culprit_action, '_CanCommitRevert', return_value=True)
  def testCommit(self, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    pipeline_input = SubmitRevertCLParameters(
        cl_key=CLKey(repo_name=repo_name, revision=revision),
        revert_status=1,
        failure_type=failure_type.COMPILE)

    self.assertEqual(gerrit.COMMITTED,
                     culprit_action.CommitRevert(pipeline_input, 'pipeline_id'))
