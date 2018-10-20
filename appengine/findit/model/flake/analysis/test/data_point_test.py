# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.analysis.data_point import DataPoint
from waterfall.test import wf_testcase


class DataPointTest(wf_testcase.WaterfallTestCase):

  def testGetPassCount(self):
    self.assertEqual(
        0,
        DataPoint.Create(pass_rate=0.0, iterations=100).GetPassCount())
    self.assertEqual(
        10,
        DataPoint.Create(pass_rate=0.5, iterations=20).GetPassCount())
    self.assertEqual(
        429,
        DataPoint.Create(pass_rate=0.9976744186046511,
                         iterations=430).GetPassCount())

  def testGetSwarmingTaskId(self):
    task_ids = ['a', 'b', 'c']
    data_point = DataPoint.Create(task_ids=task_ids)
    self.assertEqual(data_point.GetSwarmingTaskId(), 'c')
