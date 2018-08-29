# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import monitoring as common_monitoring
from common.waterfall import failure_type
from services import monitoring
from waterfall.test import wf_testcase


class MonitoringTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(common_monitoring.try_jobs, 'increment')
  def testOnTryJobTriggered(self, mock_common_monitoring):
    try_job_type = failure_type.COMPILE
    master_name = 'm'
    builder_name = 'b'
    monitoring.OnTryJobTriggered(try_job_type, master_name, builder_name)
    parameters = {
        'operation': 'trigger',
        'type': try_job_type,
        'master_name': master_name,
        'builder_name': builder_name
    }
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.culprit_found, 'increment')
  def testOnCulpritsAction(self, mock_common_monitoring):
    monitoring.OnCulpritAction('test', 'culprit_notified')
    parameters = {'type': 'test', 'action_taken': 'culprit_notified'}
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.try_job_errors, 'increment')
  def testOnTryJobError(self, mock_common_monitoring):
    try_job_type = failure_type.COMPILE
    master_name = 'm'
    builder_name = 'b'
    error_dict = {'message': 'message', 'reason': 'reason'}
    monitoring.OnTryJobError(try_job_type, error_dict, master_name,
                             builder_name)
    parameters = {
        'type': try_job_type,
        'error': error_dict.get('message', 'unknown'),
        'master_name': master_name,
        'builder_name': builder_name
    }
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.swarming_tasks, 'increment')
  def testOnSwarmingTaskStatusChange(self, mock_common_monitoring):
    monitoring.OnSwarmingTaskStatusChange('operation', 'category')
    parameters = {'operation': 'operation', 'category': 'category'}
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.issues, 'increment')
  def testOnIssueChange(self, mock_common_monitoring):
    monitoring.OnIssueChange('operation', 'category')
    parameters = {'operation': 'operation', 'category': 'category'}
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.flake_analyses, 'increment')
  def testOnFlakeCulprit(self, mock_common_monitoring):
    monitoring.OnFlakeCulprit('result', 'action_taken', 'reason')
    parameters = {
        'result': 'result',
        'action_taken': 'action_taken',
        'reason': 'reason'
    }
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.waterfall_analysis_statuses, 'increment')
  def testOnWaterfallAnalysisStateChange(self, mock_common_monitoring):
    monitoring.OnWaterfallAnalysisStateChange('m', 'b', 'compile', 'compile',
                                              'N/A', 'Completed', 'Heuristic')
    parameters = {
        'master_name': 'm',
        'builder_name': 'b',
        'failure_type': 'compile',
        'canonical_step_name': 'compile',
        'isolate_target_name': 'N/A',
        'status': 'Completed',
        'analysis_type': 'Heuristic',
    }
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.flakes, 'increment')
  def testOnFlakeAnalysisTriggered(self, mock_common_monitoring):
    monitoring.OnFlakeAnalysisTriggered('source', 'operation', 'trigger',
                                        'canonical_step_name',
                                        'isolate_target_name')
    parameters = {
        'source': 'source',
        'operation': 'operation',
        'trigger': 'trigger',
        'canonical_step_name': 'canonical_step_name',
        'isolate_target_name': 'isolate_target_name'
    }
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.flakes_identified_by_waterfall_analyses,
                     'increment_by')
  def testOnFlakeIdentified(self, mock_common_monitoring):
    monitoring.OnFlakeIdentified('canonical_step_name', 'isolate_target_name',
                                 'analyzed', 10)
    parameters = {
        'canonical_step_name': 'canonical_step_name',
        'isolate_target_name': 'isolate_target_name',
        'operation': 'analyzed',
    }
    mock_common_monitoring.assert_called_once_with(10, parameters)

  @mock.patch.object(common_monitoring.flake_detection_query_failures,
                     'increment')
  def testOnFlakeDetectionQueryFailed(self, mock_common_monitoring):
    monitoring.OnFlakeDetectionQueryFailed('cq false rejection')
    parameters = {
        'flake_type': 'cq false rejection',
    }
    mock_common_monitoring.assert_called_once_with(parameters)

  @mock.patch.object(common_monitoring.flake_detection_flake_occurrences,
                     'increment_by')
  def testOnFlakeDetectionDetectNewOccurrences(self, mock_common_monitoring):
    monitoring.OnFlakeDetectionDetectNewOccurrences('cq false rejection', 10)
    parameters = {
        'flake_type': 'cq false rejection',
    }
    mock_common_monitoring.assert_called_once_with(10, parameters)

  @mock.patch.object(common_monitoring.flake_detection_issues, 'increment')
  def testOnFlakeDetectionCreateOrUpdateIssues(self, mock_common_monitoring):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('create')
    parameters = {
        'operation': 'create',
    }
    mock_common_monitoring.assert_called_once_with(parameters)
