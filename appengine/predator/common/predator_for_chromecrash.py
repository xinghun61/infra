# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from analysis import detect_regression_range
from analysis.changelist_classifier import ChangelistClassifier
from analysis.chromecrash_parser import ChromeCrashParser
from analysis.chrome_crash_data import ChromeCrashData
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
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from common.model.inverted_index import ChromeCrashInvertedIndex
from common.predator_app import PredatorApp
from gae_libs import appengine_util
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher


class PredatorForChromeCrash(PredatorApp):  # pylint: disable=W0223
  """Find culprits for crash reports from the Chrome Crash server."""

  @classmethod
  def _ClientID(cls): # pragma: no cover
    if cls is PredatorForChromeCrash:
      logging.warning('PredatorForChromeCrash is abstract, '
          'but someone constructed an instance and called _ClientID')
    else:
      logging.warning(
          'PredatorForChromeCrash subclass %s forgot to implement _ClientID',
          cls.__name__)
    raise NotImplementedError()

  def __init__(self, get_repository, config):
    super(PredatorForChromeCrash, self).__init__(get_repository, config)
    meta_weight = MetaWeight({
        'TouchCrashedFileMeta': MetaWeight({
            'MinDistance': Weight(2.),
            'TopFrameIndex': Weight(1.),
            'TouchCrashedFile': Weight(1.),
        }),
        'TouchCrashedDirectory': Weight(1.),
        'TouchCrashedComponent': Weight(0.),
        'NumberOfTouchedFiles': Weight(0.5)
    })

    min_distance_feature = MinDistanceFeature(get_repository)
    top_frame_index_feature = TopFrameIndexFeature()
    touch_crashed_file_feature = TouchCrashedFileFeature()
    meta_feature = WrapperMetaFeature(
        [TouchCrashedFileMetaFeature([min_distance_feature,
                                      top_frame_index_feature,
                                      touch_crashed_file_feature]),
         TouchCrashedDirectoryFeature(),
         TouchCrashedComponentFeature(self._component_classifier),
         NumberOfTouchedFilesFeature()])

    self._predator = Predator(ChangelistClassifier(get_repository,
                                                   meta_feature,
                                                   meta_weight),
                              self._component_classifier,
                              self._project_classifier)

  def _Predator(self):  # pragma: no cover
    return self._predator

  def _CheckPolicy(self, crash_data):
    """Checks if ``CrashData`` meets policy requirements."""
    if not super(PredatorForChromeCrash, self)._CheckPolicy(crash_data):
      return False

    if crash_data.platform not in self.client_config[
        'supported_platform_list_by_channel'].get(crash_data.channel, []):
      # Bail out if either the channel or platform is not supported yet.
      logging.info('Analysis of channel %s, platform %s is not supported.',
                   crash_data.channel, crash_data.platform)
      return False

    return True

  def GetCrashData(self, raw_crash_data):
    """Returns parsed ``ChromeCrashData`` from raw json crash data."""
    return ChromeCrashData(raw_crash_data,
                           ChromeDependencyFetcher(self._get_repository),
                           top_n_frames=self.client_config['top_n'])


# TODO(http://crbug.com/659346): we misplaced the coverage tests; find them!
class PredatorForCracas(  # pylint: disable=W0223
    PredatorForChromeCrash): # pragma: no cover

  @classmethod
  def _ClientID(cls):
    return CrashClient.CRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Create stuff here.
    return CracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Get stuff here.
    return CracasCrashAnalysis.Get(crash_identifiers)


class PredatorForFracas(PredatorForChromeCrash):  # pylint: disable=W0223
  @classmethod
  def _ClientID(cls):
    return CrashClient.FRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Create stuff here.
    return FracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Get stuff here.
    return FracasCrashAnalysis.Get(crash_identifiers)
