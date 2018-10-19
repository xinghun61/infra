# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.flake.analysis.data_point import DataPoint
from waterfall.test import wf_testcase


class DataPointTest(wf_testcase.WaterfallTestCase):

  def testGetSwarmingTaskId(self):
    task_ids = ['a', 'b', 'c']
    data_point = DataPoint.Create(task_ids=task_ids)
    self.assertEqual(data_point.GetSwarmingTaskId(), 'c')
