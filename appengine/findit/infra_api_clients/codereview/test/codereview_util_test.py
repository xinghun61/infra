# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.rietveld import Rietveld


class CodeReviewUtilTest(testing.AppengineTestCase):

  def testGetCodeReviewForReviewOnRietveld(self):
    review_url = 'https://codereview.chromium.org/1234'
    codereview = codereview_util.GetCodeReviewForReview(review_url)
    self.assertTrue(isinstance(codereview, Rietveld))
    self.assertEqual('codereview.chromium.org', codereview._server_hostname)

  def testGetCodeReviewForReviewOnGerrit(self):
    review_url = 'https://chromium-review.googlesource.com/c/1234'
    codereview = codereview_util.GetCodeReviewForReview(review_url)
    self.assertIsNone(codereview)

  def testGetCodeReviewForInvalidReviewUrl(self):
    self.assertIsNone(codereview_util.GetCodeReviewForReview(None))

  def testGetChangeIdForReviewOnRietveld(self):
    review_url = 'https://codereview.chromium.org/1234'
    change_id = codereview_util.GetChangeIdForReview(review_url)
    self.assertEqual('1234', change_id)

  def testGetChangeIdForReviewOnGerrit(self):
    review_url = 'https://chromium-review.googlesource.com/c/1234'
    change_id = codereview_util.GetChangeIdForReview(review_url)
    self.assertIsNone(change_id)

  def testGetChangeIdForInvalidReviewUrl(self):
    self.assertIsNone(codereview_util.GetChangeIdForReview(None))
