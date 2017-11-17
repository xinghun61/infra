# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from services import culprit_action
from services.compile_failure import compile_culprit_action
from services.parameters import BuildKey
from services.parameters import CLKey
from services.parameters import CulpritActionParameters
from services.parameters import DictOfCLKeys
from services.parameters import ListOfCLKeys
from waterfall.test import wf_testcase


class CompileCulpritActionTest(wf_testcase.WaterfallTestCase):

  def testShouldTakeActionsOnCulpritByPass(self):
    master_name = compile_culprit_action._BYPASS_MASTER_NAME
    builder_name = 'b'
    build_number = 124
    parameters = CulpritActionParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        culprits=DictOfCLKeys(),
        heuristic_cls=ListOfCLKeys())
    self.assertFalse(
        compile_culprit_action.ShouldTakeActionsOnCulprit(parameters))

  @mock.patch.object(
      culprit_action, 'ShouldTakeActionsOnCulprit', return_value=True)
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
    self.assertTrue(
        compile_culprit_action.ShouldTakeActionsOnCulprit(parameters))
