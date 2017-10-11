# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.findit_http_client import FinditHttpClient
from infra_api_clients.codereview.rietveld import Rietveld
from infra_api_clients.codereview.gerrit import Gerrit

HTTP_CLIENT = FinditHttpClient()
_DEFAULT_RIETVELD_HOST = 'codereview.chromium.org'
_DEFAULT_GERRIT_HOST = 'chromium-review.googlesource.com'


def GetCodeReviewForReview(review_server_host, code_review_settings=None):
  """Returns an instance of CodeReview implementation or None if unknown."""
  if not review_server_host:
    return None

  if IsCodeReviewRietveld(review_server_host, code_review_settings):
    return Rietveld(review_server_host)
  elif IsCodeReviewGerrit(review_server_host, code_review_settings):
    return Gerrit(review_server_host)
  return None


def IsCodeReviewRietveld(review_server_host, code_review_settings=None):
  settings = code_review_settings or {}
  return review_server_host in settings.get('rietveld_hosts',
                                            [_DEFAULT_RIETVELD_HOST])


def IsCodeReviewGerrit(review_server_host, code_review_settings=None):
  settings = code_review_settings or {}
  return review_server_host in settings.get('gerrit_hosts',
                                            [_DEFAULT_GERRIT_HOST])
