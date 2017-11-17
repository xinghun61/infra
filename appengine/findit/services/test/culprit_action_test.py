# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from services import ci_failure
from services import culprit_action
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from waterfall.test import wf_testcase


class CulpritActionTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=True)
  def testShouldNotTakeActionsOnCulpritIfBuildGreen(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    cl_key = CLKey(repo_name='chromium', revision='r1')
    culprits = DictOfCLKeys()
    culprits['r1'] = cl_key
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfCLKeys())
    self.assertFalse(culprit_action.ShouldTakeActionsOnCulprit(parameters))

  @mock.patch.object(ci_failure, 'AnyNewBuildSucceeded', return_value=False)
  def testShouldTakeActionsOnCulprit(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    cl_key = CLKey(repo_name='chromium', revision='r1')
    culprits = DictOfCLKeys()
    culprits['r1'] = cl_key
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=culprits,
        heuristic_cls=ListOfCLKeys())
    self.assertTrue(culprit_action.ShouldTakeActionsOnCulprit(parameters))
