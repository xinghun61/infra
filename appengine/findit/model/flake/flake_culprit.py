# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_suspected_cl import BaseSuspectedCL


class FlakeCulprit(BaseSuspectedCL):
  """Represents information about a culprit CL for flake analysis."""

  # Url to the code review or change log associated with this change.
  url = ndb.StringProperty(indexed=False)

  # A list of urlsafe-keys to MasterFlakeAnalysis entities for which this is the
  # corresponding culprit to as confirmed by try jobs.
  flake_analysis_urlsafe_keys = ndb.StringProperty(indexed=False, repeated=True)

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, repo_name, revision, commit_position, url=None):
    instance = super(FlakeCulprit, cls).Create(repo_name, revision,
                                               commit_position)
    instance.url = url
    return instance
