# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from testing_utils import testing

from handlers import swarming_task
from model import wf_analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from waterfall import buildbot
from waterfall import waterfall_config

class SwarmingTaskTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/swarming-task', swarming_task.SwarmingTask),], debug=True)

  def setUp(self):
    super(SwarmingTaskTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121

    def MockedGetSwarmingSettings():
      return {'server_host': 'chromium-swarm.appspot.com'}
    self.mock(
        waterfall_config, 'GetSwarmingSettings', MockedGetSwarmingSettings)

  def testGenerateSwarmingTasksDataReturnEmptyIfNoFailureMap(self):
    WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number).put()

    data = swarming_task._GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGenerateSwarmingTasksDataReturnEmptyIfNoSwarmingTests(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
        'step2': '%s/%s/%s' % (
            self.master_name, self.builder_name, self.build_number)
    }
    analysis.put()

    data = swarming_task._GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGenerateSwarmingTasksDataIfNoSwarmingTask(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test2': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        },
        'step2': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120)
        }
    }
    analysis.put()

    data = swarming_task._GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': [],
            'tests': {}
        },
        'step2': {
            'swarming_tasks': [],
            'tests': {}
        }
    }
    self.assertEqual(expected_data, data)

  def testGenerateSwarmingTasksData(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test2': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        },
        'step2': {
            'test1': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        }
    }
    analysis.put()

    task0 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, 120, 'step1')
    task0.task_id = 'task0'
    task0.status = wf_analysis_status.ANALYZED
    task0.put()

    task1 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'step1')
    task1.task_id = 'task1'
    task1.status = wf_analysis_status.ANALYZED
    task1.put()

    task2 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'step2')
    task2.put()

    data = swarming_task._GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': [
                {
                    'status': 'Completed',
                    'task_id': 'task1',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task1')
                },
                {
                    'status': 'Completed',
                    'task_id': 'task0',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task0')
                }
            ],
            'tests': {
                'test1': {
                    'status': 'Completed',
                    'task_id': 'task0',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task0')
                },
                'test2': {
                    'status': 'Completed',
                    'task_id': 'task1',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task1')
                }
            }
        },
        'step2': {
            'swarming_tasks': [
                {
                    'status': 'Pending'
                }
            ],
            'tests': {
                'test1': {
                    'status': 'Pending'
                }
            }
        }
    }
    self.assertEqual(expected_data, data)

  def testSwarmingTaskHandler(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number)
    response = self.test_app.get('/swarming-task', params={'url': build_url})
    expected_results = {}

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body)
