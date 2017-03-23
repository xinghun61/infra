# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra_api_clients.codereview import codereview


class Gerrit(codereview.CodeReview):  # pragma: no cover
  """Stub for implementing Gerrit support."""
  def GetCodeReviewUrl(self, change_id):
    return 'https://%s/q/%s' % (self._server_hostname, change_id)

  def GetChangeIdForReview(self, review_url):
    raise NotImplementedError()

  # TODO(crbug.com/702681): flesh out these methods
  def PostMessage(self, change_id, message):
    raise NotImplementedError()

  def CreateRevert(self, reason, change_id, patchset_id=None):
    raise NotImplementedError()

  def AddReviewers(self, change_id, reviewers, message=None):
    raise NotImplementedError()

  def GetClDetails(self, change_id):
    raise NotImplementedError()
