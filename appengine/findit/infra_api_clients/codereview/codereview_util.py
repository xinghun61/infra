# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urlparse

from gae_libs.http.http_client_appengine import HttpClientAppengine
from infra_api_clients.codereview.rietveld import Rietveld
from infra_api_clients.codereview.gerrit import Gerrit
from waterfall import waterfall_config

HTTP_CLIENT = HttpClientAppengine()

def GetCodeReviewForReview(review_url):
  """Returns an instance of CodeReview implementation or None if unknown."""
  if not review_url:
    return None
  u = urlparse.urlparse(review_url)
  settings = waterfall_config.GetCodeReviewSettings() or {}
  # TODO(robertocn): remove these hardcoded hostnames when the config is set.
  if u.netloc in settings.get('rietveld_hosts', ['codereview.chromium.org']):
    return Rietveld(u.netloc)
  elif u.netloc in settings.get(
      'gerrit_hosts', ['chromium-review.googlesource.com']):
    return Gerrit(u.netloc)
  return None
