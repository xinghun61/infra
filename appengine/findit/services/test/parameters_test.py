# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from services import parameters
from waterfall.test import wf_testcase


class ParametersTest(wf_testcase.WaterfallTestCase):

  def testBuildKey(self):
    build_key = parameters.BuildKey(
        master_name='m', builder_name='b', build_number=1)
    self.assertEqual(('m', 'b', 1), build_key.GetParts())

  def testGFailureToCulpritMap(self):
    failure_to_culprit_map = parameters.FailureToCulpritMap.FromSerializable({
        's1': {
            's1_t1': 'key1',
            's1_t2': 'key1'
        },
        's2': {
            's2_t1': 'key2'
        }
    })
    self.assertItemsEqual(['s1', 's2'], failure_to_culprit_map.failed_steps)

    self.assertItemsEqual({
        's1': ['s1_t1', 's1_t2'],
        's2': ['s2_t1']
    }, failure_to_culprit_map.failed_steps_and_tests)
