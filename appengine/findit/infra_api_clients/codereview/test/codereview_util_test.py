# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from testing_utils import testing

from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.rietveld import Rietveld
from infra_api_clients.codereview.gerrit import Gerrit


class CodeReviewUtilTest(testing.AppengineTestCase):

  def testGetCodeReviewForReviewOnRietveld(self):
    review_host = 'codereview.chromium.org'
    codereview = codereview_util.GetCodeReviewForReview(review_host)
    self.assertTrue(isinstance(codereview, Rietveld))

  def testGetCodeReviewForReviewOnGerrit(self):
    review_host = 'chromium-review.googlesource.com'
    codereview = codereview_util.GetCodeReviewForReview(review_host)
    self.assertIsInstance(codereview, Gerrit)

  def testGetCodeReviewForInvalidReviewUrl(self):
    self.assertIsNone(codereview_util.GetCodeReviewForReview(None))
    self.assertIsNone(codereview_util.GetCodeReviewForReview('invalid.com'))