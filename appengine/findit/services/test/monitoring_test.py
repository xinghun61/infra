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