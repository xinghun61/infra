# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging

from pipeline_utils.appengine_third_party_pipeline_src_pipeline import handlers
from testing_utils import testing

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import build_failure_analysis_pipelines
from waterfall import buildbot
from waterfall import lock_util


class _MockRootPipeline(object):
  STARTED = False

  def __init__(self, master_name, builder_name, build_number):
    pass
  
  def pipeline_status_path(self):
    return ''
    
  def start(self, queue_name):
    _MockRootPipeline.STARTED = True
    logging.info(queue_name)


class BuildFailureAnalysisPipelinesTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def _CreateAndSaveWfAnalysis(
      self, master_name, builder_name, build_number, status):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = status
    analysis.put()

  def testAnalysisIsNeededWhenBuildWasNeverAnalyzed(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenNotForced(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  wf_analysis_status.ANALYZED)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNotNeededWhenForcedAndLastAnalysisIsNotCompleted(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, True)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNeededWhenForcedAndLastAnalysisIsCompleted(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZED)

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, True)

    self.assertTrue(need_analysis)

  def testStartPipelineForNewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
          
    self.mock(build_failure_analysis_pipelines.analyze_build_failure_pipeline, 
              'AnalyzeBuildFailurePipeline', 
              _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, False, 'default')

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    
    self.assertTrue(_MockRootPipeline.STARTED)
    self.assertIsNotNone(analysis)
    
  def testNotStartPipelineForNewAnalysis(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    self._CreateAndSaveWfAnalysis(
        master_name, builder_name, build_number, wf_analysis_status.ANALYZING)
      
    self.mock(build_failure_analysis_pipelines.analyze_build_failure_pipeline, 
              'AnalyzeBuildFailurePipeline', 
              _MockRootPipeline)
    _MockRootPipeline.STARTED = False

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number, False, 'default')

    self.assertFalse(_MockRootPipeline.STARTED)
