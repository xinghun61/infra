# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import tempfile
import time
import unittest

import mock

from infra.services.sysmon import puppet_metrics


class PuppetMetricsTest(unittest.TestCase):
  def setUp(self):
    puppet_metrics.reset_metrics_for_unittest()

    self.tempdir = tempfile.mkdtemp()
    self.filename = os.path.join(self.tempdir, 'last_run_summary.yaml')
    self.fh = open(self.filename, 'w')

    self.mock_lastrunfile = mock.patch(
        'infra.services.sysmon.puppet_metrics._lastrunfile').start()
    self.mock_lastrunfile.return_value = self.filename

  def tearDown(self):
    mock.patch.stopall()

    self.fh.close()
    shutil.rmtree(self.tempdir)

  def test_empty_file(self):
    puppet_metrics.get_puppet_summary()

    self.assertIs(None, puppet_metrics.config_version.get())
    self.assertIs(None, puppet_metrics.puppet_version.get())

  def test_file_not_found(self):
    self.mock_lastrunfile.return_value = os.path.join(self.tempdir, 'missing')

    puppet_metrics.get_puppet_summary()

    self.assertIs(None, puppet_metrics.config_version.get())
    self.assertIs(None, puppet_metrics.puppet_version.get())

  def test_invalid_file(self):
    self.fh.write('"')
    self.fh.close()

    puppet_metrics.get_puppet_summary()

    self.assertIs(None, puppet_metrics.config_version.get())
    self.assertIs(None, puppet_metrics.puppet_version.get())

  def test_file_contains_array(self):
    self.fh.write("""\
- one
- two
""")
    self.fh.close()

    puppet_metrics.get_puppet_summary()

    self.assertIs(None, puppet_metrics.config_version.get())
    self.assertIs(None, puppet_metrics.puppet_version.get())

  def test_summary(self):
    self.fh.write("""\
---
  version:
    config: 1440131220
    puppet: "3.6.2"
  resources:
    changed: 1
    failed: 2
    failed_to_restart: 3
    out_of_sync: 4
    restarted: 5
    scheduled: 6
    skipped: 7
    total: 51
  time:
    anchor: 0.01
    apt_key: 0.02
    config_retrieval: 0.03
    exec: 0.04
    file: 0.05
    filebucket: 0.06
    package: 0.07
    schedule: 0.08
    service: 0.08
    total: 0.09
    last_run: 1440132466
  changes:
    total: 4
  events:
    failure: 1
    success: 2
    total: 3
""")
    self.fh.close()

    mock_time = mock.create_autospec(time.time, spec_set=True)
    mock_time.return_value = 1440132466 + 123
    puppet_metrics.get_puppet_summary(time_fn=mock_time)

    self.assertEqual(1440131220, puppet_metrics.config_version.get())
    self.assertEqual('3.6.2', puppet_metrics.puppet_version.get())

    self.assertEqual(1, puppet_metrics.events.get({'result': 'failure'}))
    self.assertEqual(2, puppet_metrics.events.get({'result': 'success'}))
    self.assertEqual(None, puppet_metrics.events.get({'result': 'total'}))

    self.assertEqual(1, puppet_metrics.resources.get({'action': 'changed'}))
    self.assertEqual(2, puppet_metrics.resources.get({'action': 'failed'}))
    self.assertEqual(3, puppet_metrics.resources.get({
        'action': 'failed_to_restart'}))
    self.assertEqual(4, puppet_metrics.resources.get({'action': 'out_of_sync'}))
    self.assertEqual(5, puppet_metrics.resources.get({'action': 'restarted'}))
    self.assertEqual(6, puppet_metrics.resources.get({'action': 'scheduled'}))
    self.assertEqual(7, puppet_metrics.resources.get({'action': 'skipped'}))
    self.assertEqual(51, puppet_metrics.resources.get({'action': 'total'}))

    self.assertEqual(0.01, puppet_metrics.times.get({'step': 'anchor'}))
    self.assertEqual(0.02, puppet_metrics.times.get({'step': 'apt_key'}))
    self.assertEqual(0.03, puppet_metrics.times.get({
        'step': 'config_retrieval'}))
    self.assertEqual(0.04, puppet_metrics.times.get({'step': 'exec'}))
    self.assertEqual(0.05, puppet_metrics.times.get({'step': 'file'}))
    self.assertEqual(0.06, puppet_metrics.times.get({'step': 'filebucket'}))
    self.assertEqual(0.07, puppet_metrics.times.get({'step': 'package'}))
    self.assertEqual(0.08, puppet_metrics.times.get({'step': 'schedule'}))
    self.assertEqual(0.08, puppet_metrics.times.get({'step': 'service'}))
    self.assertEqual(None, puppet_metrics.times.get({'step': 'total'}))
    self.assertEqual(123, puppet_metrics.age.get())

  def test_summary_missing_sections(self):
    self.fh.write("""\
---
  something_else:
    foo: 123
    bar: 456
""")
    self.fh.close()

    mock_time = mock.create_autospec(time.time, spec_set=True)
    mock_time.return_value = 1440132466 + 123
    puppet_metrics.get_puppet_summary(time_fn=mock_time)

    self.assertEqual(None, puppet_metrics.config_version.get())
    self.assertEqual(None, puppet_metrics.puppet_version.get())
