# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto import swarming_task_error
from dto.swarming_task_error import SwarmingTaskError
from gae_libs.testcase import TestCase


class SwarmingTaskErrorTest(TestCase):

  def testGenerateError(self):
    expected_error = {'code': 1000, 'message': 'Unknown error'}
    self.assertEqual(expected_error,
                     SwarmingTaskError.GenerateError(
                         swarming_task_error.UNKNOWN).ToSerializable())
