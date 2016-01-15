# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from infra_libs import ts_mon
from infra.services.sysmon import cipd_metrics


DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class TestListCipdVersions(unittest.TestCase):
  def test_no_version_files(self):
    cipd_version_dir = os.path.join(DATA_DIR, 'empty')
    paths = cipd_metrics.list_cipd_versions(cipd_version_dir)
    self.assertEqual(paths, [])

  def test_python_cipd_version(self):
    cipd_version_dir = os.path.join(DATA_DIR, 'python_version')
    paths = cipd_metrics.list_cipd_versions(cipd_version_dir)
    self.assertEqual(paths,
                     [os.path.join(cipd_version_dir, 'CIPD_VERSION.json')])

  def test_cipd_version(self):
    cipd_version_dir = os.path.join(DATA_DIR, 'all_versions')
    paths = cipd_metrics.list_cipd_versions(cipd_version_dir)
    paths.sort()
    self.assertEqual(paths,
                     [os.path.join(cipd_version_dir, 'tool1.cipd_version'),
                      os.path.join(cipd_version_dir, 'tool2.cipd_version')])


class TestReadCipdVersion(unittest.TestCase):
  def test_read_valid_file(self):
    cipd_version_file = os.path.join(DATA_DIR,
                                     'python_version',
                                     'CIPD_VERSION.json')
    version = cipd_metrics.read_cipd_version(cipd_version_file)
    self.assertIsInstance(version, dict)
    self.assertIn('instance_id', version)
    self.assertEqual(version['instance_id'],
                             '92b4bc62bfe83e4e31f2a6ce42bd58edbfd442cd')
    self.assertIn('package_name', version)
    self.assertEqual(version['package_name'],
                     'infra/infra_python/linux-amd64-ubuntu12_04')

  def test_read_invalid_json(self):
    cipd_version_file = os.path.join(DATA_DIR,
                                     'invalid_files',
                                     'invalid_json.cipd_version')
    version = cipd_metrics.read_cipd_version(cipd_version_file)
    self.assertIs(version, None)

  def test_read_missing_package_name(self):
    cipd_version_file = os.path.join(DATA_DIR,
                                     'invalid_files',
                                     'missing_package_name.cipd_version')
    version = cipd_metrics.read_cipd_version(cipd_version_file)
    self.assertIs(version, None)

  def test_read_missing_instance_id(self):
    cipd_version_file = os.path.join(DATA_DIR,
                                     'invalid_files',
                                     'missing_instance_id.cipd_version')
    version = cipd_metrics.read_cipd_version(cipd_version_file)
    self.assertIs(version, None)

class TestGetCipdSummary(unittest.TestCase):
  def setUp(self):
    self.old_all_version_files = cipd_metrics.ALL_VERSION_DIRS
    ts_mon.reset_for_unittest()

  def tearDown(self):
    cipd_metrics.ALL_VERSION_DIRS = self.old_all_version_files

  def test_empty_directories(self):
    cipd_metrics.ALL_VERSION_DIRS = {
      'default': [os.path.join(DATA_DIR, 'empty')]
    }
    cipd_metrics.get_cipd_summary()
    # TODO(pgervais,577931) This does not test much since it will return None
    # when a value has been pushed with a metric field.
    self.assertEqual(None, cipd_metrics.package_instance_id.get())

  def test_single_file(self):
    cipd_metrics.ALL_VERSION_DIRS = {
      'default': [os.path.join(DATA_DIR, 'python_version')]
    }
    cipd_metrics.get_cipd_summary()
    self.assertEqual('92b4bc62bfe83e4e31f2a6ce42bd58edbfd442cd',
                     cipd_metrics.package_instance_id.get(
                       {'package_name':
                        'infra/infra_python/linux-amd64-ubuntu12_04'}
                      ))

  def test_multiple_files(self):
    cipd_metrics.ALL_VERSION_DIRS = {
      'default': [os.path.join(DATA_DIR, 'all_versions')]
    }
    cipd_metrics.get_cipd_summary()
    self.assertEqual(
      'deadbeefgfe83e4e31f2a6ce42bd58edbfd442cd',
      cipd_metrics.package_instance_id.get({'package_name': 'tool1'})
    )
    self.assertEqual(
      'beefdeadgfe83e4e31f2a6ce42bd58edbfd442cd',
      cipd_metrics.package_instance_id.get({'package_name': 'tool2'})
    )


  def test_invalid_files(self):
    cipd_metrics.ALL_VERSION_DIRS = {
      'default': [os.path.join(DATA_DIR, 'invalid_files')]
    }
    cipd_metrics.get_cipd_summary()
    self.assertEqual(None, cipd_metrics.package_instance_id.get())
