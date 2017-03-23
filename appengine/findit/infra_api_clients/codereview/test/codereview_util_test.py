# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.rietveld import Rietveld
from infra_api_clients.codereview.gerrit import Gerrit
from waterfall.test.wf_testcase import WaterfallTestCase


class CodeReviewUtilTest(WaterfallTestCase):

  def testGetCodeReviewForReviewOnRietveld(self):
    review_url = 'https://codereview.chromium.org/1234'
    codereview = codereview_util.GetCodeReviewForReview(review_url)
    self.assertTrue(isinstance(codereview, Rietveld))
    self.assertEqual('codereview.chromium.org', codereview._server_hostname)

  def testGetCodeReviewForReviewOnGerrit(self):
    review_url = 'https://chromium-review.googlesource.com/c/1234'
    codereview = codereview_util.GetCodeReviewForReview(review_url)
    self.assertIsInstance(codereview, Gerrit)

  def testGetCodeReviewForInvalidReviewUrl(self):
    self.assertIsNone(codereview_util.GetCodeReviewForReview(None))
    self.assertIsNone(codereview_util.GetCodeReviewForReview('invalid.com'))

  def testGetChangeIdForReviewOnRietveld(self):
    review_url = 'https://codereview.chromium.org/1234'
    codereview = codereview_util.GetCodeReviewForReview(review_url)
    change_id = codereview.GetChangeIdForReview(review_url)
    self.assertEqual('1234', change_id)

  def testGetChangeIdForReviewOnGerrit(self):
    review_url = 'https://chromium-review.googlesource.com/c/1234'
    with self.assertRaises(NotImplementedError):
      codereview = codereview_util.GetCodeReviewForReview(review_url)
      _ = codereview.GetChangeIdForReview(review_url)
