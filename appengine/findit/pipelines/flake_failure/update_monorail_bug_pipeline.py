# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles all bug-related calls for flake analysis."""

from google.appengine.ext import ndb

from common import monitoring
from gae_libs import appengine_util
from gae_libs.pipelines import SynchronousPipeline
from libs.structured_object import StructuredObject
from monorail_api import IssueTrackerAPI
from services import issue_tracking_service
from services.flake_failure import flake_constants
from services.flake_failure import flake_report_util


class UpdateMonorailBugInput(StructuredObject):
  # The urlsafe key to the MasterFlakeAnalysis.
  analysis_urlsafe_key = basestring


class UpdateMonorailBugPipeline(SynchronousPipeline):
  """Logs or updates attached bugs with flake analysis results."""
  input_type = UpdateMonorailBugInput
  output_type = bool

  def RunImpl(self, parameters):
    """Updates existing mororail bugs with flake analysis results.

    Returns:
      (bool) Whether or not a bug was updated.
    """
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis

    if not flake_report_util.ShouldUpdateBugForAnalysis(analysis):
      return False

    project_name = flake_constants.CHROMIUM_PROJECT_NAME
    issue_tracker = IssueTrackerAPI(
        project_name, use_staging=appengine_util.IsStaging())
    issue = issue_tracking_service.TraverseMergedIssues(analysis.bug_id,
                                                        issue_tracker)
    if not issue:
      analysis.LogWarning(
          'Bug %s/%s or the merged-into one may have been deleted!' %
          (project_name, analysis.bug_id))

      if analysis.culprit_urlsafe_key:
        monitoring.flake_analyses.increment({
            # There is a culprit, but there is no bug to update.
            'result': 'culprit-identified',
            'action_taken': 'none',
            'reason': 'missing-bug-not-updated',
        })

      return False

    comment = flake_report_util.GenerateBugComment(analysis)
    issue_tracking_service.AddFinditLabelToIssue(issue)

    monitoring.issues.increment({'operation': 'update', 'category': 'flake'})
    if analysis.culprit_urlsafe_key:
      monitoring.flake_analyses.increment({
          'result': 'culprit-identified',
          'action_taken': 'bug-updated',
          'reason': ''
      })

    issue_tracker.update(issue, comment, send_email=True)
    analysis.Update(has_commented_on_bug=True)
    analysis.LogInfo('Bug %s/%s was updated.' % (project_name, analysis.bug_id))
    return True
