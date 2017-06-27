# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.changelist_classifier import ChangelistClassifier
from analysis.linear.feature import WrapperMetaFeature
from analysis.linear.weight import MetaWeight
from analysis.predator import Predator
from analysis.type_enums import CrashClient
from analysis.uma_sampling_profiler_data import UMASamplingProfilerData
from common.model.uma_sampling_profiler_analysis import (
    UMASamplingProfilerAnalysis)
from common.predator_app import PredatorApp
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher


# TODO(cweakliam): There are currently no heuristics for the UMA Sampling
# Profiler, so this is not yet used. It will be used once those are developed.
class PredatorForUMASamplingProfiler(PredatorApp):
  """Finds culprits for regressions/improvements from UMA Sampling Profiler."""

  @classmethod
  def _ClientID(cls):
    return CrashClient.UMA_SAMPLING_PROFILER

  def __init__(self, get_repository, config):
    super(PredatorForUMASamplingProfiler, self).__init__(get_repository, config)
    meta_weight = MetaWeight({
        # weights go here
    })
    meta_feature = WrapperMetaFeature([
        # features go here
    ])

    self._predator = Predator(ChangelistClassifier(get_repository,
                                                   meta_feature,
                                                   meta_weight),
                              self._component_classifier,
                              self._project_classifier)

  def _Predator(self):
    return self._predator

  def CreateAnalysis(self, regression_identifiers):
    """Creates ``UMASamplingProfilerAnalysis``.

    regression_identifiers is used as the key.
    """
    return UMASamplingProfilerAnalysis.Create(regression_identifiers)

  def GetAnalysis(self, regression_identifiers):
    """Gets ``UMASamplingProfilerAnalysis`` using regression_identifiers."""
    return UMASamplingProfilerAnalysis.Get(regression_identifiers)

  def GetCrashData(self, raw_regression_data):
    """Gets ``UMASamplingProfilerData`` from ``raw_regression_data``."""
    return UMASamplingProfilerData(
        raw_regression_data, ChromeDependencyFetcher(self._get_repository))
