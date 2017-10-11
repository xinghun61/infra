# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb

from monorail_api import IssueTrackerAPI

from common import monitoring
from gae_libs.pipeline_wrapper import BasePipeline


def _GetIssue(bug_id, issue_tracker):
  """Returns the issue of the given bug.

  Traverse if the bug was merged into another."""
  issue = issue_tracker.getIssue(bug_id)
  checked_issues = {}
  while issue and issue.merged_into:
    logging.info('%s was merged into %s' % (issue.id, issue.merged_into))
    checked_issues[issue.id] = issue
    issue = issue_tracker.getIssue(issue.merged_into)
    if issue.id in checked_issues:
      break  # Break the loop.
  return issue


_COMMENT_FOOTER = """
Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).
Flake Analyzer is in alpha version.
Feedback is welcome using component Tools>Test>FindIt>Flakiness !""".lstrip()

_LINK = 'https://findit-for-me.appspot.com/waterfall/flake?key=%s'

_ERROR_COMMENT_TEMPLATE = ("""
Oops, due to an error, only a partial flakiness trend was generated for
the config "%s / %s":""".lstrip().replace('\n', ' ') + '\n\n' + _LINK + '\n\n' +
                           _COMMENT_FOOTER)

_CULPRIT_COMMENT_TEMPLATE = ("""
Findit identified the culprit r%s with confidence %.1f%% in the config "%s / %s"
based on the flakiness trend:""".lstrip() + '\n\n' + _LINK + '\n\n' +
                             _COMMENT_FOOTER)

_BUILD_HIGH_CONFIDENCE_COMMENT_TEMPLATE = ("""
Findit found the flake started in build %s of the config "%s / %s"
with confidence %.1f%% based on the flakiness trend:""".lstrip() + '\n\n' +
                                           _LINK + '\n\n' + _COMMENT_FOOTER)

_LOW_FLAKINESS_COMMENT_TEMPLATE = ("""
This flake is a longstanding one, with low flakiness, or not reproducible
based on the flakiness trend in the config "%s / %s":""".lstrip() + '\n\n' +
                                   _LINK + '\n\n' + _COMMENT_FOOTER)

_FINDIT_ANALYZED_LABEL_TEXT = 'Test-Findit-Analyzed'


def _GenerateComment(analysis):
  """Generates a comment based on the analysis result."""
  if analysis.failed:
    return _ERROR_COMMENT_TEMPLATE % (analysis.original_master_name,
                                      analysis.original_builder_name,
                                      analysis.key.urlsafe(),)
  elif analysis.culprit_urlsafe_key is not None:
    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
    assert culprit
    assert analysis.confidence_in_culprit is not None
    return _CULPRIT_COMMENT_TEMPLATE % (culprit.commit_position,
                                        analysis.confidence_in_culprit * 100,
                                        analysis.original_master_name,
                                        analysis.original_builder_name,
                                        analysis.key.urlsafe(),)
  elif (analysis.suspected_flake_build_number and
        analysis.confidence_in_suspected_build > 0.6):
    return _BUILD_HIGH_CONFIDENCE_COMMENT_TEMPLATE % (
        analysis.suspected_flake_build_number, analysis.original_master_name,
        analysis.original_builder_name,
        analysis.confidence_in_suspected_build * 100, analysis.key.urlsafe(),)
  else:
    return _LOW_FLAKINESS_COMMENT_TEMPLATE % (analysis.original_master_name,
                                              analysis.original_builder_name,
                                              analysis.key.urlsafe(),)


def _LogBugNotUpdated(reason):
  logging.info('Bug not updated: %s', reason)


def _ShouldUpdateBugForAnalysis(analysis):
  if analysis.error:
    _LogBugNotUpdated('error in analysis: %s' % analysis.error.get('message'))
    monitoring.flake_analyses.increment({
        'result': 'culprit-not-identified',
        'action_taken': 'none',
        'reason': 'error',
    })
    return False

  if not analysis.completed:
    monitoring.flake_analyses.increment({
        'result': 'culprit-not-identified',
        'action_taken': 'none',
        'reason': 'analysis-incomplete',
    })
    _LogBugNotUpdated('completed=%s' % analysis.completed)
    return False

  if not analysis.bug_id:
    _LogBugNotUpdated('bug=%s' % analysis.bug_id)
    if analysis.culprit_urlsafe_key:
      monitoring.flake_analyses.increment({
          'result': 'culprit-identified',
          'action_taken': 'none',
          'reason': 'no-bug-to-update',
      })
    else:
      monitoring.flake_analyses.increment({
          'result': 'culprit-not-identified',
          'action_taken': 'none',
          'reason': 'no-bug-to-update',
      })
    return False

  if len(analysis.data_points) < 2:
    _LogBugNotUpdated('%d data points' % len(analysis.data_points))
    monitoring.flake_analyses.increment({
        'result': 'culprit-not-identified',
        'action_taken': 'none',
        'reason': 'insufficient-datapoints',
    })
    return False

  if analysis.suspected_flake_build_number is None:
    _LogBugNotUpdated('no regression range identifed')
    monitoring.flake_analyses.increment({
        'result': 'culprit-not-identified',
        'action_taken': 'none',
        'reason': 'no-regression-range-indentified',
    })
    return False

  if not analysis.algorithm_parameters.get('update_monorail_bug'):
    _LogBugNotUpdated('update_monorail_bug not set or is False')
    if analysis.culprit_urlsafe_key:
      monitoring.flake_analyses.increment({
          # There is a culprit, but updating bugs is disabled.
          'result': 'culprit-identified',
          'action_taken': 'none',
          'reason': 'update-bug-disabled',
      })
    else:
      monitoring.flake_analyses.increment({
          # There is a culprit, but updating bugs is disabled.
          'result': 'culprit-not-identified',
          'action_taken': 'none',
          'reason': 'update-bug-disabled',
      })
    return False

  if (not analysis.culprit_urlsafe_key and
      analysis.confidence_in_suspected_build < analysis.algorithm_parameters.
      get('minimum_confidence_score_to_run_tryjobs')):
    _LogBugNotUpdated('insufficient confidence in suspected build')
    monitoring.flake_analyses.increment({
        'result': 'culprit-not-identified',
        'action_taken': 'none',
        'reason': 'insufficient-confidence',
    })
    return False

  return True


class UpdateFlakeBugPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_flake_analysis_key):
    """Updates the attached bug of the flake with the analysis result.

    Args:
      urlsafe_flake_analysis_key (str): The urlsafe-key of the
          MasterFlakeAnalysis.
    """
    analysis = ndb.Key(urlsafe=urlsafe_flake_analysis_key).get()
    assert analysis

    if not _ShouldUpdateBugForAnalysis(analysis):
      return False

    project_name = 'chromium'
    is_staging = app_identity.get_application_id().endswith('-staging')
    issue_tracker = IssueTrackerAPI(project_name, use_staging=is_staging)
    issue = _GetIssue(analysis.bug_id, issue_tracker)
    if not issue:
      logging.warn('Bug %s/%s or the merged-into one seems deleted!',
                   project_name, analysis.bug_id)
      if analysis.culprit_urlsafe_key:
        monitoring.flake_analyses.increment({
            # There is a culprit, but there is no bug to update.
            'result': 'culprit-identified',
            'action_taken': 'none',
            'reason': 'missing-bug-not-updated',
        })
      return False

    comment = _GenerateComment(analysis)

    # Since a flake bug may be updated twice, once when the regression range
    # is identified and again when a culprit is identified, ensure the
    # 'Test-Findit-Analyzed' label is only present once.
    if _FINDIT_ANALYZED_LABEL_TEXT not in issue.labels:  # pragma: no branch
      issue.labels.append(_FINDIT_ANALYZED_LABEL_TEXT)

    monitoring.issues.increment({'operation': 'update', 'category': 'flake'})
    if analysis.culprit_urlsafe_key:
      monitoring.flake_analyses.increment({
          'result': 'culprit-identified',
          'action_taken': 'bug-updated',
          'reason': ''
      })

    issue_tracker.update(issue, comment, send_email=True)
    logging.info('Bug %s/%s was updated.', project_name, analysis.bug_id)
    return True
