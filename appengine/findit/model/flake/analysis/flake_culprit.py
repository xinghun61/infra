# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from google.appengine.ext import ndb

from model.base_suspected_cl import BaseSuspectedCL
from waterfall import buildbot


class FlakeCulprit(BaseSuspectedCL):
  """Represents information about a culprit CL for flake analysis."""

  # Url to the code review or change log associated with this change.
  url = ndb.StringProperty(indexed=False)

  # A list of urlsafe-keys to MasterFlakeAnalysis entities for which this is the
  # corresponding culprit to as confirmed by try jobs.
  flake_analysis_urlsafe_keys = ndb.StringProperty(indexed=False, repeated=True)

  # The key to the associated FlakeIssue. Should be set only once, as subsequent
  # analyses that identify this same culprit should merge issues into this one.
  flake_issue_key = ndb.KeyProperty('FlakeIssue')

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, repo_name, revision, commit_position, url=None):
    instance = super(FlakeCulprit, cls).Create(repo_name, revision,
                                               commit_position)
    instance.url = url
    return instance

  def GetCulpritLink(self):
    return ('https://analysis.chromium.org/p/chromium/flake-portal/analysis/'
            'culprit?key=%s' % self.key.urlsafe())

  def GenerateRevertReason(self,
                           build_id,
                           commit_position,
                           revision,
                           sample_step_name=None):
    # pylint: disable=unused-argument
    analysis = ndb.Key(urlsafe=self.flake_analysis_urlsafe_keys[-1]).get()
    assert analysis

    sample_build = build_id.split('/')
    sample_build_url = buildbot.CreateBuildUrl(*sample_build)
    return textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
        culprit for flakes in the build cycles as shown on:
        https://analysis.chromium.org/p/chromium/flake-portal/analysis/culprit?key=%s\n
        Sample Failed Build: %s\n
        Sample Failed Step: %s\n
        Sample Flaky Test: %s""") % (
        commit_position or revision,
        self.key.urlsafe(),
        sample_build_url,
        analysis.original_step_name,
        analysis.original_test_name,
    )
