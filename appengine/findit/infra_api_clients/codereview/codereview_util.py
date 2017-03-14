# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urlparse

from infra_api_clients.codereview.rietveld import Rietveld


def GetCodeReviewForReview(review_url):
  """Returns an instance of CodeReview implementation or None if unknown."""
  if not review_url:
    return None
  u = urlparse.urlparse(review_url)
  if u.netloc == 'codereview.chromium.org':  # TODO(stgao): move to config.
    return Rietveld(u.netloc)
  return None


def GetChangeIdForReview(review_url):
  """Returns the change id or issue number of the review or None if unknown."""
  if not review_url:
    return None
  u = urlparse.urlparse(review_url)
  if u.netloc == 'codereview.chromium.org':
    return u.path.split('/')[-1]
  return None
