# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

_DEFAULT_GERRIT_HOST = 'chromium-review.googlesource.com'


def IsCodeReviewGerrit(review_server_host, code_review_settings=None):
  settings = code_review_settings or {}
  return review_server_host in settings.get('gerrit_hosts',
                                            [_DEFAULT_GERRIT_HOST])
