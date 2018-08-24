# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import mock

from common import monitoring
from common.waterfall import failure_type
from dto.dict_of_basestring import DictOfBasestring
from infra_api_clients.codereview import codereview_util
from libs import analysis_status
from libs.list_of_basestring import ListOfBasestring
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from services import constants
from services import culprit_action
from services import gerrit
from services import git
from services import irc
from services.parameters import BuildKey
from services.parameters import CreateRevertCLParameters
from services.parameters import CulpritActionParameters
from services.parameters import SendNotificationForCulpritParameters
from services.parameters import SendNotificationToIrcParameters
from services.parameters import SubmitRevertCLParameters
from waterfall.test import wf_testcase


class CulpritActionTest(wf_testcase.WaterfallTestCase):

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
    self.assertFalse(culprit_action.ShouldTakeActionsOnCulprit(parameters))

  @mock.patch.object(
      ci_failure,
      'GetLaterBuildsWithAnySameStepFailure',
      return_value={125: ['a']})
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
    self.assertTrue(culprit_action.ShouldTakeActionsOnCulprit(parameters))

  def testShouldForceNotify(self):
    cl_key = 'mockurlsafekey'

    culprit_dict = DictOfBasestring()
    culprit_dict['rev1'] = cl_key

    heuristic_cls = ListOfBasestring()
    heuristic_cls.append(cl_key)

    parameters_dict = {
        'build_key': {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 123
        },
        'culprits': {
            'rev1': culprit_dict
        },
        'heuristic_cls': heuristic_cls
    }
    self.assertTrue(
        culprit_action.ShouldForceNotify(
            cl_key, CulpritActionParameters.FromSerializable(parameters_dict)))

  def testRevertHasCompleted(self):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = analysis_status.COMPLETED
    culprit.put()

    parameters = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(), build_id='build_id')
    pipeline_id = 'pipeline_id'

    self.assertFalse(
        culprit_action._CanCreateRevertForCulprit(parameters, pipeline_id))

  def testRevertACulpritIsBeingReverted(self):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_status = analysis_status.RUNNING
    culprit.revert_pipeline_id = 'pipeline_id'
    culprit.put()

    parameters = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(), build_id='build_id')
    pipeline_id = 'another_pipeline'

    self.assertFalse(
        culprit_action._CanCreateRevertForCulprit(parameters, pipeline_id))

  def test_CanCreateRevertForCulprit(self):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_status = analysis_status.RUNNING
    culprit.put()

    parameters = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(), build_id='build_id')
    pipeline_id = 'pipeline_id'

    self.assertTrue(
        culprit_action._CanCreateRevertForCulprit(parameters, pipeline_id))

  def testCannotCommitRevertIfNotRevertByFindit(self):
    parameters = SubmitRevertCLParameters(
        cl_key='mockurlsafekey', revert_status=constants.CREATED_BY_SHERIFF)
    pipeline_id = 'pipeline_id'

    self.assertFalse(
        culprit_action._CanCommitRevert(parameters, pipeline_id,
                                        'codereview_info'))

  @mock.patch.object(git, 'ChangeCommittedWithinTime', return_value=True)
  @mock.patch.object(git, 'IsAuthoredByNoAutoRevertAccount', return_value=False)
  @mock.patch.object(gerrit, 'ExistCQedDependingChanges', return_value=False)
  def testCanCommitRevert(self, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = analysis_status.COMPLETED
    culprit.put()

    parameters = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(), revert_status=constants.CREATED_BY_FINDIT)
    pipeline_id = 'pipeline_id'

    self.assertTrue(
        culprit_action._CanCommitRevert(parameters, pipeline_id,
                                        'codereview_info'))

  def testCannotCommitRevertByAnotherAnalysis(self):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.revert_cl = RevertCL()
    culprit.revert_status = analysis_status.COMPLETED
    culprit.revert_submission_status = analysis_status.RUNNING
    culprit.submit_revert_pipeline_id = 'pipeline_id'
    culprit.put()

    parameters = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(), revert_status=constants.CREATED_BY_FINDIT)
    pipeline_id = 'another_pipeline'

    self.assertFalse(
        culprit_action._CanCommitRevert(parameters, pipeline_id,
                                        'codereview_info'))

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionCreated(self, mock_mo):
    culprit_action.MonitorRevertAction(
        failure_type.COMPILE, constants.CREATED_BY_FINDIT, constants.SKIPPED)
    parameters = {'type': 'compile', 'action_taken': 'revert_created'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionConfirmed(self, mock_mo):
    culprit_action.MonitorRevertAction(
        failure_type.COMPILE, constants.CREATED_BY_SHERIFF, constants.SKIPPED)
    parameters = {'type': 'compile', 'action_taken': 'revert_confirmed'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionSkipped(self, mock_mo):
    culprit_action.MonitorRevertAction(failure_type.COMPILE, constants.SKIPPED,
                                       constants.SKIPPED)
    self.assertFalse(mock_mo.called)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionError(self, mock_mo):
    culprit_action.MonitorRevertAction(failure_type.COMPILE, constants.ERROR,
                                       constants.SKIPPED)
    parameters = {'type': 'compile', 'action_taken': 'revert_status_error'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorRevertActionSubmitted(self, mock_mo):
    culprit_action.MonitorRevertAction(
        failure_type.COMPILE, constants.CREATED_BY_FINDIT, constants.COMMITTED)
    parameters = {'type': 'compile', 'action_taken': 'revert_committed'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testMonitorCommitRevertActionError(self, mock_mo):
    culprit_action.MonitorRevertAction(
        failure_type.COMPILE, constants.CREATED_BY_FINDIT, constants.ERROR)
    parameters = {'type': 'compile', 'action_taken': 'revert_commit_error'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  @mock.patch.object(irc, 'SendMessageToIrc')
  def testNoNeedToSendNotification(self, mocked_irc, mock_mo):
    revert_status = constants.CREATED_BY_SHERIFF
    commit_status = constants.SKIPPED
    pipeline_input = SendNotificationToIrcParameters(
        cl_key='mockurlsafekey',
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendMessageToIRC(pipeline_input))
    self.assertFalse(mocked_irc.called)
    parameters = {'type': 'compile', 'action_taken': 'irc_notified_skip'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  @mock.patch.object(irc, 'SendMessageToIrc')
  def testSendNotificationNoCulprit(self, mocked_irc, mock_mo):
    revert_status = constants.CREATED_BY_FINDIT
    commit_status = constants.ERROR
    pipeline_input = SendNotificationToIrcParameters(
        cl_key='mockurlsafekey',
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendMessageToIRC(pipeline_input))

    self.assertFalse(mocked_irc.called)
    parameters = {'type': 'compile', 'action_taken': 'irc_notified_error'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(monitoring.culprit_found, 'increment')
  @mock.patch.object(irc, 'SendMessageToIrc')
  def testSendNotificationNoRevert(self, mocked_irc, mock_mo):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = constants.CREATED_BY_FINDIT
    commit_status = constants.ERROR

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.put()

    pipeline_input = SendNotificationToIrcParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendMessageToIRC(pipeline_input))

    self.assertFalse(mocked_irc.called)
    parameters = {'type': 'compile', 'action_taken': 'irc_notified_error'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(irc, 'SendMessageToIrc', return_value=True)
  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testSendNotificationToIRC(self, mock_mo, _):
    repo_name = 'chromium'
    revision = 'rev'
    revert_status = constants.CREATED_BY_FINDIT
    commit_status = constants.SKIPPED

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.revert_cl = RevertCL()
    culprit.revert_cl.revert_cl_url = 'revert_url'
    culprit.put()

    pipeline_input = SendNotificationToIrcParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=revert_status,
        commit_status=commit_status,
        failure_type=failure_type.COMPILE)
    self.assertTrue(culprit_action.SendMessageToIRC(pipeline_input))
    parameters = {'type': 'compile', 'action_taken': 'irc_notified'}
    mock_mo.assert_called_once_with(parameters)

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
                                               constants.CREATED_BY_SHERIFF, 2))
    self.assertFalse(
        culprit_action._ShouldSendNotification('chromium', 'r2', True,
                                               constants.CREATED_BY_SHERIFF, 2))
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
                                               constants.CREATED_BY_FINDIT, 2))
    self.assertFalse(culprit.cr_notification_processed)

  @mock.patch.object(
      culprit_action, '_ShouldSendNotification', return_value=False)
  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testShouldNotSendNotificationForCulprit(self, mock_mo, _):
    repo_name = 'chromium'
    revision = 'rev1'
    force_notify = True
    revert_status = constants.CREATED_BY_SHERIFF

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.put()

    pipeline_input = SendNotificationForCulpritParameters(
        cl_key=culprit.key.urlsafe(),
        force_notify=force_notify,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    self.assertFalse(culprit_action.SendNotificationForCulprit(pipeline_input))
    parameters = {'type': 'compile', 'action_taken': 'culprit_notified_skip'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(
      culprit_action, 'GetCodeReviewDataForACulprit', return_value={})
  @mock.patch.object(gerrit, 'SendNotificationForCulprit', return_value=True)
  @mock.patch.object(
      culprit_action, '_ShouldSendNotification', return_value=True)
  @mock.patch.object(monitoring.culprit_found, 'increment')
  def testSendNotification(self, mock_mo, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    force_notify = True
    revert_status = constants.CREATED_BY_SHERIFF

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.put()

    pipeline_input = SendNotificationForCulpritParameters(
        cl_key=culprit.key.urlsafe(),
        force_notify=force_notify,
        revert_status=revert_status,
        failure_type=failure_type.COMPILE)
    self.assertTrue(culprit_action.SendNotificationForCulprit(pipeline_input))
    parameters = {'type': 'compile', 'action_taken': 'culprit_notified'}
    mock_mo.assert_called_once_with(parameters)

  @mock.patch.object(
      culprit_action, '_CanCreateRevertForCulprit', return_value=False)
  def testRevertCulpritSkipped(self, _):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.put()

    pipeline_input = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        build_id=build_id,
        failure_type=failure_type.COMPILE)
    self.assertEqual(
        constants.SKIPPED,
        culprit_action.RevertCulprit(pipeline_input, 'pipeline_id'))

  @mock.patch.object(
      culprit_action, 'GetCodeReviewDataForACulprit', return_value={})
  @mock.patch.object(
      culprit_action, '_CanCreateRevertForCulprit', return_value=True)
  @mock.patch.object(gerrit, 'RevertCulprit')
  def testRevertCulprit(self, mock_revert, *_):
    repo_name = 'chromium'
    revision = 'rev1'
    build_id = 'm/b/123'

    revert_cl = RevertCL()
    revert_cl.revert_cl_url = 'url'
    revert_cl.created_time = datetime.datetime(2018, 6, 20, 0, 0, 0)

    mock_revert.return_value = (constants.CREATED_BY_FINDIT, revert_cl, None)

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.put()

    pipeline_input = CreateRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        build_id=build_id,
        failure_type=failure_type.COMPILE)
    self.assertEqual(
        constants.CREATED_BY_FINDIT,
        culprit_action.RevertCulprit(pipeline_input, 'pipeline_id'))
    culprit = WfSuspectedCL.Get(repo_name, revision)
    self.assertEqual(revert_cl, culprit.revert_cl)
    self.assertEqual(analysis_status.COMPLETED, culprit.revert_status)

  @mock.patch.object(
      culprit_action, 'GetCodeReviewDataForACulprit', return_value=None)
  @mock.patch.object(culprit_action, '_CanCommitRevert', return_value=False)
  def testCommitSkipped(self, *_):
    repo_name = 'chromium'
    revision = 'rev1'

    culprit = WfSuspectedCL.Create(repo_name, revision, 1)
    culprit.put()

    pipeline_input = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=constants.CREATED_BY_FINDIT,
        failure_type=failure_type.COMPILE)

    self.assertEqual(constants.SKIPPED,
                     culprit_action.CommitRevert(pipeline_input, 'pipeline_id'))

  @mock.patch.object(
      culprit_action, 'GetCodeReviewDataForACulprit', return_value={})
  @mock.patch.object(gerrit, 'CommitRevert', return_value=constants.COMMITTED)
  @mock.patch.object(culprit_action, '_CanCommitRevert', return_value=True)
  def testCommit(self, *_):
    culprit = WfSuspectedCL.Create('chromium', 'rev1', 1)
    culprit.put()

    pipeline_input = SubmitRevertCLParameters(
        cl_key=culprit.key.urlsafe(),
        revert_status=constants.CREATED_BY_FINDIT,
        failure_type=failure_type.COMPILE)

    self.assertEqual(constants.COMMITTED,
                     culprit_action.CommitRevert(pipeline_input, 'pipeline_id'))

    culprit = WfSuspectedCL.Get('chromium', 'rev1')
    self.assertEqual(analysis_status.COMPLETED,
                     culprit.revert_submission_status)

  def testGetSampleFailedStepName(self):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    build_id = 'm/b/123'
    culprit.builds = {build_id: {'failures': {'step': ['test1', 'test2']}}}
    culprit.put()
    self.assertEqual(
        'step',
        culprit_action.GetSampleFailedStepName(repo_name, revision, build_id))

  @mock.patch.object(logging, 'warning')
  def testGetSampleFailedStepNameUseAnotherBuild(self, mock_log):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    build_id = 'm/b/123'
    culprit.builds = {'m/b/124': {'failures': {'step': ['test1', 'test2']}}}
    culprit.put()
    self.assertEqual(
        'step',
        culprit_action.GetSampleFailedStepName(repo_name, revision, build_id))
    mock_log.assert_called_once_with(
        '%s is not found in culprit %s/%s\'s build,'
        ' using another build to get a sample failed step.', build_id,
        repo_name, revision)

  @mock.patch.object(logging, 'error')
  def testGetSampleFailedStepNameFailed(self, mock_log):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    build_id = 'm/b/123'
    culprit.builds = None
    culprit.put()
    self.assertEqual(
        '', culprit_action.GetSampleFailedStepName(repo_name, revision,
                                                   build_id))
    mock_log.assert_called_once_with(
        'Cannot get a sample failed step for culprit %s/%s.', repo_name,
        revision)

  @mock.patch.object(
      codereview_util, 'GetCodeReviewForReview', return_value=None)
  @mock.patch.object(git, 'GetCodeReviewInfoForACommit')
  def testGetCodeReviewDataForACulprit(self, mock_change_info, _):
    repo_name = 'chromium'
    revision = 'rev1'
    culprit = WfSuspectedCL.Create(repo_name, revision, 123)
    culprit.put()

    code_review_data = {
        'commit_position': 123,
        'code_review_url': 'url',
        'review_server_host': 'host',
        'review_change_id': '123',
        'author': {
            'name': 'author',
            'email': 'author@abc.com'
        },
        'committer': {
            'name': 'committer',
            'email': 'committer@abc.com'
        },
    }
    mock_change_info.return_value = code_review_data
    self.assertEqual(
        code_review_data,
        culprit_action.GetCodeReviewDataForACulprit(culprit.key.urlsafe()))
