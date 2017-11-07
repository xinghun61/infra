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
    """
    analysis = ndb.Key(urlsafe=input_object.analysis_urlsafe_key).get()
    assert analysis

    analysis.LogInfo('RunImpl being called for CreateBugForFlakePipeline')

    if not issue_tracking_service.ShouldFileBugForAnalysis(analysis):
      return

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

    # TODO(crbug.com/780110): Use customized field for querying for duplicates.

    # TODO(crbug.com/780111): Limit the number of bugs filed per day.

    # TODO(crbug.com/780112): Check if a test is disabled before filing.

    # TODO(crbug.com/780113): Verify test is still flaky in recent build.
