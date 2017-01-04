# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
from infra_libs import ts_mon

import infra.tools.master_manager.__main__ as mm

class MasterManagerTest(unittest.TestCase):

  def setUp(self):
    super(MasterManagerTest, self).setUp()
    ts_mon.reset_for_unittest()

  @mock.patch('subprocess.check_call', autospec=True)
  @mock.patch('subprocess.check_output', autospec=True)
  def test_run(self, check_output_mock, check_call_mock):
    mastermap_json = [{
        'fullhost': 'master.host.name',
        'dirname': 'master.dir',
    }]
    check_output_mock.return_value = json.dumps(mastermap_json)
    # Dry run execution.
    self.assertEqual(0, mm.run([
        '/path/master.dir', 'running', '1000',
        '--hostname', 'master.host.name']))
    self.assertFalse(check_call_mock.called)

    # Production run.
    self.assertEqual(0, mm.run([
        '/path/master.dir', 'running', '1000',
        '--hostname', 'master.host.name', '--prod']))
    self.assertEqual(1, check_call_mock.call_count)
    self.assertEqual(2, mm.run_count.get(
        fields={'result': 'success', 'action': '_make_start'}))


class ParseArgsTest(unittest.TestCase):
  def setUp(self):
    self.mock_logs = (
        mock.patch('infra_libs.logs.process_argparse_options').start())
    self.mock_ts_mon = (
        mock.patch('infra_libs.ts_mon.process_argparse_options').start())

  def tearDown(self):
    mock.patch.stopall()

  def test_ts_mon_task_job_name(self):
    args = mm.parse_args(['/foo/bar/baz', 'running', '123'])
    self.assertEqual('baz', args.ts_mon_task_job_name)

    self.assertEqual(1, self.mock_ts_mon.call_count)
    args = self.mock_ts_mon.call_args[0][0]
    self.assertEqual('baz', args.ts_mon_task_job_name)

  def test_explicit_ts_mon_task_job_name(self):
    args = mm.parse_args(['--ts-mon-task-job-name', 'wibble',
                          '/foo/bar/baz', 'running', '123'])
    self.assertEqual('wibble', args.ts_mon_task_job_name)

    self.assertEqual(1, self.mock_ts_mon.call_count)
    args = self.mock_ts_mon.call_args[0][0]
    self.assertEqual('wibble', args.ts_mon_task_job_name)

  def test_list_all_states(self):
    mm.parse_args(['--list-all-states'])  # Should not error
    self.assertFalse(self.mock_ts_mon.called)

  def test_missing_directory(self):
    with self.assertRaises(SystemExit):
      mm.parse_args(['', 'running', '123'])

  def test_missing_state(self):
    with self.assertRaises(SystemExit):
      mm.parse_args(['/foo/bar/baz', '', '123'])

  def test_missing_transition_time(self):
    with self.assertRaises(SystemExit):
      mm.parse_args(['/foo/bar/baz', 'running', '0'])
