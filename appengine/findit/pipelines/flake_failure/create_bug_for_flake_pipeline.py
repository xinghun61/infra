# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import logging
import datetime

from google.appengine.ext import ndb
from gae_libs.pipelines import GeneratorPipeline
from libs import time_util
from libs.structured_object import StructuredObject

from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.flake_culprit import FlakeCulprit

from services.flake_failure import issue_tracking_service

from waterfall.flake import flake_constants
from waterfall.flake import triggering_sources

SUBJECT_TEMPLATE = '%s is Flaky'
BODY_TEMPLATE = ('Findit has detected a flake at test %s. Track this'
                 'analysis here:\n%s')


def _HasPreviousAttempt(analysis):
  """Returns true if filing a bug has been attempted before."""
  return analysis.has_attempted_filing


def _HasSufficientConfidenceInCulprit(analysis):
  """Returns true is there's enough confidence in the culprit."""
  if not analysis.confidence_in_culprit:
    return False
  return (abs(analysis.confidence_in_culprit -
              flake_constants.MINIMUM_CONFIDENCE_TO_CREATE_BUG) <= 0.001)


class CreateBugForFlakePipelineInputObject(StructuredObject):
  analysis_urlsafe_key = unicode
  test_location = dict


class CreateBugForFlakePipeline(GeneratorPipeline):

  input_type = CreateBugForFlakePipelineInputObject

  def RunImpl(self, input_object):
    """Creates a bug for a flake analysis.

    Creates a bug if certain conditions are satisfied. These conditions are
    logically unordered, and the ordering you see in the pipeline is to
    favor local operations over network requests. This pipeline shouldn't
    be retried since it files a bug with monorail. Instead a bit is set
    in MasterFlakeAnalysis before a filing is attempted `has_attemped_filing`
    in the event in a retry this pipeline will be abandoned entirely.

    Ths requirements for a bug to be filed.
    - The pipeline hasn't been attempted before (see above).
    - The analysis has sufficient confidence (1.0).
    - The analysis doesn't already have a bug associated with it.
    - A bug isn't open for the same test.
    """
    analysis = ndb.Key(urlsafe=input_object.analysis_urlsafe_key).get()
    assert analysis

    analysis.LogInfo('RunImpl being called for CreateBugForFlakePipeline')

    # TODO(crbug.com/773870): Factor these conditions to the service layer.
    if _HasPreviousAttempt(analysis):
      analysis.LogWarning(
          'There has already been an attempt at filing a bug, aborting.')
      return

    if not _HasSufficientConfidenceInCulprit(analysis):
      analysis.LogInfo('Bailing out because %d isn\'t high enough confidence' %
                       analysis.confidence_in_culprit)
      return

    # Check if there's already a bug attached to this issue.
    if issue_tracking_service.BugAlreadyExistsForId(analysis.bug_id):
      analysis.LogInfo(
          'Bailing out because bug with id %d already exists' % analysis.bug_id)
      return

    if issue_tracking_service.BugAlreadyExistsForLabel(analysis.test_name):
      analysis.LogInfo('Bailing out because bug already exists for label %s' %
                       analysis.test_name)
      return

    # TODO(crbug.com/773526): Make sure the test is enabled and flaky on recent
    # build.

    subject = SUBJECT_TEMPLATE % analysis.test_name

    analysis_link = ('https://findit-for-me.appspot.com/waterfall/flake?key=%s'
                     % input_object.analysis_urlsafe_key)
    body = BODY_TEMPLATE % (analysis.test_name, analysis_link)

    # Log our attempt in analysis so we don't retry perpetually.
    analysis.Update(has_attempted_filing=True)
    bug_id = issue_tracking_service.CreateBugForTest(analysis.test_name,
                                                     subject, body)
    if not bug_id:
      analysis.LogError('Couldn\'t create bug!')
      return

    analysis.Update(bug_id=bug_id)
    analysis.LogInfo('Filed bug with id %d' % bug_id)

    flake_analysis_request = FlakeAnalysisRequest.GetVersion(
        key=analysis.test_name)
    assert flake_analysis_request
    flake_analysis_request.Update(
        bug_reported_by=triggering_sources.FINDIT_PIPELINE, bug_id=bug_id)
