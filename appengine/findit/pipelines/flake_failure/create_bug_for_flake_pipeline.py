# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import logging
import datetime

from google.appengine.ext import ndb
from gae_libs import pipelines
from gae_libs.pipelines import pipeline

from common.findit_http_client import FinditHttpClient
from libs import time_util
from libs.structured_object import StructuredObject
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.flake_culprit import FlakeCulprit
from services.flake_failure import issue_tracking_service
from waterfall import build_util
from waterfall import swarming_util
from waterfall.flake import flake_constants
from waterfall.flake import triggering_sources
from waterfall.flake.analyze_flake_for_build_number_pipeline import (
    AnalyzeFlakeForBuildNumberPipeline)
from waterfall.flake.lookback_algorithm import IsFullyStable

_SUBJECT_TEMPLATE = '%s is Flaky'
_BODY_TEMPLATE = ('Findit has detected a flake at test %s. Track this'
                  'analysis here:\n%s')

# TODO(crbug.com/783335): Allow these values to be configurable.
_ITERATIONS_TO_CONFIRM_FLAKE = 30  # 30 iterations.
_ITERATIONS_TO_CONFIRM_FLAKE_TIMEOUT = 60 * 60  # One hour.


class CreateBugForFlakePipelineInputObject(StructuredObject):
  analysis_urlsafe_key = unicode
  test_location = dict


class CreateBugForFlakePipeline(pipelines.GeneratorPipeline):

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

    if not issue_tracking_service.ShouldFileBugForAnalysis(analysis):
      return

    most_recent_build_number = build_util.GetLatestBuildNumber(
        analysis.master_name, analysis.builder_name)
    if not most_recent_build_number:
      analysis.LogInfo('Bug not failed because latest build number not found.')
      return

    tasks = swarming_util.ListSwarmingTasksDataByTags(
        analysis.master_name, analysis.builder_name, most_recent_build_number,
        FinditHttpClient(), {'stepname': analysis.step_name})
    if not tasks:
      analysis.LogInfo('Bug not filed because no recent runs found.')
      return

    task = tasks[0]
    if not swarming_util.IsTestEnabled(analysis.test_name, task['task_id']):
      analysis.LogInfo('Bug not filed because test was fixed or disabled.')
      return

    analysis_pipeline = yield AnalyzeFlakeForBuildNumberPipeline(
        input_object.analysis_urlsafe_key, most_recent_build_number,
        _ITERATIONS_TO_CONFIRM_FLAKE, _ITERATIONS_TO_CONFIRM_FLAKE_TIMEOUT,
        True)
    with pipeline.After(analysis_pipeline):
      next_input_object = pipelines.CreateInputObjectInstance(
          _CreateBugIfStillFlakyInputObject,
          analysis_urlsafe_key=input_object.analysis_urlsafe_key,
          most_recent_build_number=most_recent_build_number)
      yield _CreateBugIfStillFlaky(next_input_object)

    # TODO(crbug.com/780110): Use customized field for querying for duplicates.


class _CreateBugIfStillFlakyInputObject(StructuredObject):
  analysis_urlsafe_key = unicode
  most_recent_build_number = int


class _CreateBugIfStillFlaky(pipelines.GeneratorPipeline):
  input_type = _CreateBugIfStillFlakyInputObject

  def RunImpl(self, input_object):
    analysis = ndb.Key(urlsafe=input_object.analysis_urlsafe_key).get()
    assert analysis

    data_point = analysis.FindMatchingDataPointWithBuildNumber(
        input_object.most_recent_build_number)

    # If we're out of bounds of the lower or upper flake threshold, this test
    # is stable (either passing or failing consistently).
    if not data_point or IsFullyStable(data_point.pass_rate):
      analysis.LogInfo('Bug not filed because test is stable in latest build.')
      return

    subject = _SUBJECT_TEMPLATE % analysis.test_name
    analysis_link = ('https://findit-for-me.appspot.com/waterfall/flake?key=%s'
                     % input_object.analysis_urlsafe_key)
    body = _BODY_TEMPLATE % (analysis.test_name, analysis_link)

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
