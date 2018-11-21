# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from model.flake.flake import Flake
from services import flake_util
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeUtilTest(WaterfallTestCase):

  @mock.patch.object(Flake, 'NormalizeStepName')
  @mock.patch.object(Flake, 'NormalizeTestName')
  @mock.patch.object(Flake, 'Create')
  def testGetFlakeExisting(self, mocked_create, mocked_test_name,
                           mocked_step_name):
    luci_project = 'chromium'
    step_name = 'step_name'
    test_name = 'test_name'
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    label = 'label'
    mocked_test_name.return_value = test_name
    mocked_step_name.return_value = step_name

    flake = Flake.Create(luci_project, step_name, test_name, label)
    flake.put()

    self.assertEqual(
        flake,
        flake_util.GetFlake(luci_project, step_name, test_name, master_name,
                            builder_name, build_number))
    mocked_create.assert_not_called()

  @mock.patch.object(Flake, 'NormalizeStepName')
  @mock.patch.object(Flake, 'NormalizeTestName')
  def testGetFlake(self, mocked_test_name, mocked_step_name):
    luci_project = 'chromium'
    step_name = 'step_name'
    test_name = 'test_name'
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    mocked_test_name.return_value = test_name
    mocked_step_name.return_value = step_name

    self.assertIsNotNone(
        flake_util.GetFlake(luci_project, step_name, test_name, master_name,
                            builder_name, build_number))
