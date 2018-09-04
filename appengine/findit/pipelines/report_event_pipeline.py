# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs import pipelines
from libs import structured_object
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.wf_analysis import WfAnalysis
from services import event_reporting


def _CanReportAnalysis(analysis):
  """Returns True if the analysis can be reported, False otherwise."""
  return analysis.start_time and analysis.end_time


class ReportEventInput(structured_object.StructuredObject):
  """Represents a urlsafe key for the analysis to be reported."""
  analysis_urlsafe_key = basestring


class ReportAnalysisEventPipeline(pipelines.GeneratorPipeline):
  """Pipeline to report events after analysis completion."""
  input_type = ReportEventInput

  def RunImpl(self, parameters):
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis

    if not _CanReportAnalysis(analysis):
      logging.warning(
          'Error reporting analysis %s: \nCanReportAnalysis returned False.',
          parameters.analysis_urlsafe_key)
      return

    success = False
    if isinstance(analysis, MasterFlakeAnalysis):
      success = event_reporting.ReportTestFlakeAnalysisCompletionEvent(analysis)
    elif isinstance(analysis, WfAnalysis):
      if analysis.build_failure_type == failure_type.COMPILE:
        success = event_reporting.ReportCompileFailureAnalysisCompletionEvent(
            analysis)
      elif analysis.build_failure_type == failure_type.TEST:
        success = event_reporting.ReportTestFailureAnalysisCompletionEvent(
            analysis)

    if not success:
      logging.error('Error reporting analysis %s', analysis.key.urlsafe())

    return
