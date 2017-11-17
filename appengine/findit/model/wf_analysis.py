# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import constants
from common.waterfall import failure_type
from libs import analysis_status
from model import result_status
from model.base_build_model import BaseBuildModel


class WfAnalysis(BaseBuildModel):
  """Represents an analysis of a build of a builder in a Chromium waterfall.

  'Wf' is short for waterfall.
  """

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number):  # pragma: no cover
    return ndb.Key('WfAnalysis',
                   BaseBuildModel.CreateBuildId(master_name, builder_name,
                                                build_number))

  @staticmethod
  def Create(master_name, builder_name, build_number):  # pragma: no cover
    analysis = WfAnalysis(key=WfAnalysis._CreateKey(master_name, builder_name,
                                                    build_number))
    analysis.failure_result_map = analysis.failure_result_map or {}
    return analysis

  @staticmethod
  def Get(master_name, builder_name, build_number):  # pragma: no cover
    return WfAnalysis._CreateKey(master_name, builder_name, build_number).get()

  @property
  def completed(self):
    return self.status in (analysis_status.COMPLETED, analysis_status.ERROR)

  @property
  def duration(self):
    if not self.completed or not self.end_time or not self.start_time:
      return None

    return int((self.end_time - self.start_time).total_seconds())

  @property
  def failed(self):
    return self.status == analysis_status.ERROR

  @property
  def status_description(self):
    return analysis_status.STATUS_TO_DESCRIPTION.get(self.status, 'Unknown')

  @property
  def result_status_description(self):
    return result_status.RESULT_STATUS_TO_DESCRIPTION.get(
        self.result_status, '')

  @property
  def correct(self):
    """Returns whether the analysis result is correct or not.

    Returns:
      True: correct
      False: incorrect
      None: don't know yet.
    """
    if not self.completed or self.failed:
      return None

    if self.result_status in (result_status.FOUND_CORRECT,
                              result_status.NOT_FOUND_CORRECT,
                              result_status.FOUND_CORRECT_DUPLICATE):
      return True

    if self.result_status in (result_status.FOUND_INCORRECT,
                              result_status.NOT_FOUND_INCORRECT,
                              result_status.FOUND_INCORRECT_DUPLICATE):
      return False

    return None

  @property
  def is_duplicate(self):
    """Returns whether the analysis result is a duplicate or not."""

    return self.result_status in (result_status.FOUND_CORRECT_DUPLICATE,
                                  result_status.FOUND_INCORRECT_DUPLICATE)

  def Reset(self):  # pragma: no cover
    """Resets to the state as if no analysis is run."""
    self.pipeline_status_path = None
    self.status = analysis_status.PENDING
    self.aborted = False
    self.request_time = None
    self.start_time = None
    self.end_time = None
    self.failure_result_map = self.failure_result_map or {}

  @property
  def failure_type(self):
    if self.build_failure_type is not None:
      return self.build_failure_type

    # Legacy data don't have property ``build_failure_type``.
    if not self.result:
      return failure_type.UNKNOWN

    step_failures = self.result.get('failures', [])
    if not step_failures:
      return failure_type.UNKNOWN

    for step_result in step_failures:
      if step_result['step_name'] == constants.COMPILE_STEP_NAME:
        return failure_type.COMPILE

    # Although the failed steps could be infra setup steps like "bot_update",
    # for legacy data we just assume all of them are tests if not compile.
    return failure_type.TEST

  @property
  def failure_type_str(self):
    return failure_type.GetDescriptionForFailureType(self.failure_type)

  # When the build cycle started.
  build_start_time = ndb.DateTimeProperty(indexed=True)
  # Whether the build cycle has completed.
  build_completed = ndb.BooleanProperty(indexed=False)
  # Whether it is a compile failure, test failure, infra failure or others.
  # Refer to common/waterfall/failure_type.py for all the failure types.
  build_failure_type = ndb.IntegerProperty(indexed=True)

  # The url path to the pipeline status page.
  pipeline_status_path = ndb.StringProperty(indexed=False)
  # The status of the analysis.
  status = ndb.IntegerProperty(default=analysis_status.PENDING, indexed=False)
  # When the analysis was requested.
  request_time = ndb.DateTimeProperty(indexed=False)
  # When the analysis actually started.
  start_time = ndb.DateTimeProperty(indexed=False)
  # When the analysis actually ended.
  end_time = ndb.DateTimeProperty(indexed=False)
  # When the analysis was updated.
  updated_time = ndb.DateTimeProperty(indexed=False, auto_now=True)
  # Record which version of analysis.
  version = ndb.StringProperty(indexed=False)

  # Whether any sub-pipeline of Heuristic or try-job analysis was aborted.
  aborted = ndb.BooleanProperty(indexed=True, default=False)

  # Analysis result for the build failure.
  not_passed_steps = ndb.StringProperty(indexed=False, repeated=True)
  result = ndb.JsonProperty(indexed=False, compressed=True)
  # Suspected CLs we found.
  suspected_cls = ndb.JsonProperty(indexed=False, compressed=True)
  # Record the id of try job results of each failure.
  failure_result_map = ndb.JsonProperty(indexed=False, compressed=True)

  # The actual culprit CLs that are responsible for the failures.
  culprit_cls = ndb.JsonProperty(indexed=False, compressed=True)
  # Conclusion of analysis result for the build failure: 'Found' or 'Not Found'.
  result_status = ndb.IntegerProperty(indexed=True)
  # Record the history of triage.
  triage_history = ndb.JsonProperty(indexed=False, compressed=True)
  # Whether the triage history was obscured.
  triage_email_obscured = ndb.BooleanProperty(indexed=True, default=True)
  # When was the last addition of triage record.
  triage_record_last_add = ndb.DateTimeProperty(indexed=True)
  # Master name of the analysis the result status might be derived from.
  triage_reference_analysis_master_name = ndb.StringProperty(indexed=False)
  # Builder name of the analysis the result status might be derived from.
  triage_reference_analysis_builder_name = ndb.StringProperty(indexed=False)
  # Build number of the analysis the result status might be derived from.
  triage_reference_analysis_build_number = ndb.IntegerProperty(indexed=False)

  # The id of the failure group. Currently, this is the
  # [master_name, builder_name, build_number] of the build failure that opened
  # the failure_group. Example: ['m', 'b1', 1].
  failure_group_key = ndb.JsonProperty(indexed=False)

  # Failure info, result of DetectFirtstFailurePipeline.
  failure_info = ndb.JsonProperty(indexed=False)
  # Signals, result of ExtractSignalPipeline.
  signals = ndb.JsonProperty(indexed=False)

  def UpdateWithTryJobResult(self, updated_result_status, updated_suspected_cls,
                             updated_result):
    if (self.result_status != updated_result_status or
        self.suspected_cls != updated_suspected_cls or
        self.result != updated_result):
      self.result_status = updated_result_status
      self.suspected_cls = updated_suspected_cls
      self.result = updated_result
      self.put()
