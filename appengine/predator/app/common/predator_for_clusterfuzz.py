# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from analysis.changelist_classifier import ChangelistClassifier
from analysis.clusterfuzz_data import ClusterfuzzData
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.linear.changelist_features.number_of_touched_files import (
    NumberOfTouchedFilesFeature)
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.changelist_features.top_frame_index import (
    TopFrameIndexFeature)
from analysis.linear.changelist_features.touch_crashed_component import (
    TouchCrashedComponentFeature)
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryFeature)
from analysis.linear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
from analysis.linear.feature import WrapperMetaFeature
from analysis.linear.weight import MetaWeight
from analysis.linear.weight import Weight
from analysis.predator import Predator
from analysis.type_enums import CrashClient
from common.predator_app import PredatorApp
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis


class PredatorForClusterfuzz(PredatorApp):
  @classmethod
  def _ClientID(cls):
    return CrashClient.CLUSTERFUZZ

  def __init__(self, get_repository, config):
    super(PredatorForClusterfuzz, self).__init__(get_repository, config)
    meta_weight = MetaWeight({
        'TouchCrashedFileMeta': MetaWeight({
            'MinDistance': Weight(1.),
            'TopFrameIndex': Weight(1.),
            'TouchCrashedFile': Weight(1.),
        }),
        'TouchCrashedDirectory': Weight(1.),
        'TouchCrashedComponent': Weight(1.)
    })

    min_distance_feature = MinDistanceFeature(get_repository)
    top_frame_index_feature = TopFrameIndexFeature()
    touch_crashed_file_feature = TouchCrashedFileFeature()

    meta_feature = WrapperMetaFeature(
        [TouchCrashedFileMetaFeature([min_distance_feature,
                                      top_frame_index_feature,
                                      touch_crashed_file_feature]),
         TouchCrashedDirectoryFeature(),
         TouchCrashedComponentFeature(self._component_classifier)])

    self._predator = Predator(ChangelistClassifier(get_repository,
                                                   meta_feature,
                                                   meta_weight),
                              self._component_classifier,
                              self._project_classifier)

  def _Predator(self):  # pragma: no cover
    return self._predator

  def CreateAnalysis(self, crash_identifiers):
    """Creates ``ClusterfuzzAnalysis`` with crash_identifiers as key."""
    return ClusterfuzzAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    """Gets ``ClusterfuzzAnalysis`` using crash_identifiers."""
    return ClusterfuzzAnalysis.Get(crash_identifiers)

  def GetCrashData(self, raw_crash_data):
    """Gets ``ClusterfuzzData`` from ``raw_crash_data``."""
    return ClusterfuzzData(raw_crash_data)

  def ProcessResultForPublishing(self, result, key):  # pylint: disable=W0613
    """Clusterfuzz specific processing of result data for publishing."""
    # TODO(katesonia) Add feedback page link information to result after
    # feedback page of Clusterfuzz is added.
    return result  # pragma: no cover
