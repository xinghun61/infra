# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from parameterized import parameterized
from testing_utils import testing

from infra_api_clients.codereview import codereview_util


class CodeReviewUtilTest(testing.AppengineTestCase):

  @parameterized.expand([
      ('chromium-review.googlesource.com', True),
      (None, False),
      ('invalid.com', False),
  ])
  def testIsCodeReviewGerrit(self, review_host, is_codereivew_gerrit):
    self.assertEqual(is_codereivew_gerrit,
                     codereview_util.IsCodeReviewGerrit(review_host))
