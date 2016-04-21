# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
from infra_libs import ts_mon

import infra.tools.master_manager.__main__ as mm

class TestMasterManager(unittest.TestCase):

  def setUp(self):
    super(TestMasterManager, self).setUp()
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
        fields={'result': 'success', 'action': '_make_start'},
        target_fields={'job_name': 'master.dir'}))
                                         
