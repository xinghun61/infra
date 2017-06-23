# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_suspected_cl import BaseSuspectedCL


class FlakeCulprit(BaseSuspectedCL):
  """Represents information about a culprit CL for flake analysis."""

  # Triage status for whether the CL is correct or not.
  status = ndb.IntegerProperty(indexed=True, default=None)

  # Url to the code review or change log associated with this change.
  url = ndb.StringProperty(indexed=False)

  # The confidence in the culprit to have introduced the flakiness.
  confidence = ndb.FloatProperty(indexed=False)

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, repo_name, revision, commit_position, url,
             confidence=None):  # pragma: no cover
    instance = super(FlakeCulprit, cls).Create(repo_name, revision,
                                               commit_position)
    instance.url = url
    instance.confidence = confidence
    return instance

  def ToDict(self):
    return {
        'commit_position': self.commit_position,
        'confidence': self.confidence,
        'repo_name': self.repo_name,
        'revision': self.revision,
        'status': self.status,
        'url': self.url,
    }
