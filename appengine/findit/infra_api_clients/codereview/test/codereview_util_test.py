# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from testing_utils import testing

from infra_api_clients.codereview import codereview_util
from infra_api_clients.codereview.rietveld import Rietveld
from infra_api_clients.codereview.gerrit import Gerrit


class CodeReviewUtilTest(testing.AppengineTestCase):

  code_review_settings = {
    'rietveld_hosts': ['test-rietveld.com'],
    'gerrit_hosts': ['test-gerrit.com'],
    'commit_bot_emails': ['bot@sourcecode.com'],
  }

  def testGetCodeReviewForReviewOnRietveld(self):
    review_url = 'https://test-rietveld.com/1234'
    codereview = codereview_util.GetCodeReviewForReview(
      review_url, self.code_review_settings)
    self.assertTrue(isinstance(codereview, Rietveld))
    self.assertEqual('test-rietveld.com', codereview._server_hostname)

  def testGetCodeReviewForReviewOnGerrit(self):
    review_url = 'https://test-gerrit.com/c/1234'
    codereview = codereview_util.GetCodeReviewForReview(
      review_url, self.code_review_settings)
    self.assertIsInstance(codereview, Gerrit)

  def testGetCodeReviewForInvalidReviewUrl(self):
    self.assertIsNone(codereview_util.GetCodeReviewForReview(None))
    self.assertIsNone(codereview_util.GetCodeReviewForReview('invalid.com'))
