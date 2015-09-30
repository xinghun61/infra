# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from infra.tools.metric_tool import metric_tool
from infra_libs import temporary_directory


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


class MainMetricToolTest(unittest.TestCase):
  def test_smoke_main(self):
    metric_tool.main(DATA_DIR)


class DescriptionExtractionTest(unittest.TestCase):
  def test_extract_normal_case(self):
    descriptions = metric_tool.extract_metrics_descriptions(
      os.path.join(DATA_DIR, 'normal_case.py'))

    self.assertEqual(len(descriptions), len(metric_tool.METRICS_NAMES))
    # Cheap way of testing we're retrieving the correct strings.
    for filename, _, name, desc in descriptions:
      self.assertTrue(filename.endswith('normal_case.py'))
      self.assertTrue(name.endswith(desc))

  def test_extract_normal_case_2(self):
    descriptions = metric_tool.extract_metrics_descriptions(
      os.path.join(DATA_DIR, 'normal_case_2.py'))

    self.assertEqual(len(descriptions), len(metric_tool.METRICS_NAMES))
    # Cheap way of testing we're retrieving the correct strings.
    for filename, _, name, desc in descriptions:
      self.assertTrue(filename.endswith('normal_case_2.py'))
      self.assertTrue(name.endswith(desc))

  def test_missing_descriptions(self):
    descriptions = metric_tool.extract_metrics_descriptions(
      os.path.join(DATA_DIR, 'missing_descriptions.py'))

    self.assertEqual(len(descriptions), 9)

    self.assertEqual(sum([desc[3] is None for desc in descriptions]), 5)
    self.assertEqual(sum([desc[3] is not None for desc in descriptions]), 4)

    # Cheap way of testing we're retrieving the correct strings.
    for filename, _, name, desc in descriptions:
      self.assertTrue(filename.endswith('missing_descriptions.py'))
      self.assertTrue(desc is None or name.endswith(desc))

  def test_metric_name_not_a_string(self):
    descriptions = metric_tool.extract_metrics_descriptions(
      os.path.join(DATA_DIR, 'metric_name_not_a_string.py'))
    self.assertEqual(len(descriptions), 1)
    self.assertEqual(descriptions[0][2], 'DYNAMIC')
    self.assertEqual(descriptions[0][3], 'metric1')

  def test_missing_file(self):
    descriptions = metric_tool.extract_metrics_descriptions(
      os.path.join(DATA_DIR, 'should_not_exist.py'))
    self.assertEqual(descriptions, [])

  def test_invalid_syntax(self):
    with temporary_directory(prefix='metric_tool-') as tempdir:
      tempfile = os.path.join(tempdir, 'invalid_syntax.py')
      with open(tempfile, 'w') as f:
        f.write('=1\n')

      descriptions = metric_tool.extract_metrics_descriptions(tempfile)

    self.assertEqual(descriptions, [])

  def test_other_tests(self):
    descriptions = metric_tool.extract_metrics_descriptions(
      os.path.join(DATA_DIR, 'other_tests.py'))
    self.assertEqual(len(descriptions), 1)
    description = descriptions[0]
    self.assertEqual(description[2], '/my/metric')
    self.assertEqual(description[3], None)
