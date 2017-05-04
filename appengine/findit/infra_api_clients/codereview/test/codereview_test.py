# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from infra_api_clients.codereview import codereview


class RietveldTest(testing.AppengineTestCase):
  def testIsAutoRevertOff(self):
    test_cases = {
        'NOAUTOREVERT=TRUE': True,
        'NOAUTOREVERT = TRUE': True,
        'NOAUTOREVERT= True': True,
        'NOAUTOREVERT = true': True,
        'noautorevert = true': False,
        'NoAutoRevert=True': False,
        'string must fail': False
    }

    for case, expected_result in test_cases.iteritems():
      self.assertEqual(expected_result, codereview.IsAutoRevertOff(case))