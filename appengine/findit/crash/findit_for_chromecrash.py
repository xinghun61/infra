# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import appengine_util
from common.chrome_dependency_fetcher import ChromeDependencyFetcher
from crash import detect_regression_range
from crash.chromecrash_parser import ChromeCrashParser
from crash.chrome_crash_data import ChromeCrashData
from crash.findit import Findit
from crash.loglinear.changelist_classifier import LogLinearChangelistClassifier
from crash.loglinear.changelist_features.touch_crashed_component import (
    TouchCrashedComponentFeature)
from crash.loglinear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryFeature)
from crash.loglinear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
from crash.loglinear.feature import WrapperMetaFeature
from crash.loglinear.weight import MetaWeight
from crash.loglinear.weight import Weight
from crash.predator import Predator
from crash.type_enums import CrashClient
from model.crash.cracas_crash_analysis import CracasCrashAnalysis
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

# TODO(katesonia): Remove the default value after adding validity check to
# config.
_FRACAS_FEEDBACK_URL_TEMPLATE = 'https://%s/crash/fracas-result-feedback?key=%s'


class FinditForChromeCrash(Findit):  # pylint: disable=W0223
  """Find culprits for crash reports from the Chrome Crash server."""

  @classmethod
  def _ClientID(cls): # pragma: no cover
    if cls is FinditForChromeCrash:
      logging.warning('FinditForChromeCrash is abstract, '
          'but someone constructed an instance and called _ClientID')
    else:
      logging.warning(
          'FinditForChromeCrash subclass %s forgot to implement _ClientID',
          cls.__name__)
    raise NotImplementedError()

  def __init__(self, get_repository, config):
    super(FinditForChromeCrash, self).__init__(get_repository, config)
    meta_weight = MetaWeight({
        'TouchCrashedFileMeta': MetaWeight({
            'MinDistance': Weight(1.),
            'TopFrameIndex': Weight(1.),
            'TouchCrashedFile': Weight(1.),
        }),
        'TouchCrashedDirectory': Weight(1.),
        'TouchCrashedComponent': Weight(1.)
    })
    meta_feature = WrapperMetaFeature(
        [TouchCrashedFileMetaFeature(get_repository),
         TouchCrashedDirectoryFeature(),
         TouchCrashedComponentFeature(self._component_classifier)])

    self._predator = Predator(LogLinearChangelistClassifier(get_repository,
                                                            meta_feature,
                                                            meta_weight),
                              self._component_classifier,
                              self._project_classifier)

  def _Predator(self):  # pragma: no cover
    return self._predator

  def _CheckPolicy(self, crash_data):
    """Checks if ``CrashData`` meets policy requirements."""
    if not super(FinditForChromeCrash, self)._CheckPolicy(crash_data):
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
class FinditForCracas(  # pylint: disable=W0223
    FinditForChromeCrash): # pragma: no cover

  @classmethod
  def _ClientID(cls):
    return CrashClient.CRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Create stuff here.
    return CracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Get stuff here.
    return CracasCrashAnalysis.Get(crash_identifiers)

  def ProcessResultForPublishing(self, result, key):  # pragma: no cover.
    """Cracas specific processing of result data for publishing."""
    # TODO(katesonia) Add feedback page link information to result after
    # feedback page of Cracas is added.
    return result


class FinditForFracas(FinditForChromeCrash):  # pylint: disable=W0223
  @classmethod
  def _ClientID(cls):
    return CrashClient.FRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Create stuff here.
    return FracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Get stuff here.
    return FracasCrashAnalysis.Get(crash_identifiers)

  def ProcessResultForPublishing(self, result, key):
    """Fracas specific processing of result data for publishing."""
    result['feedback_url'] = _FRACAS_FEEDBACK_URL_TEMPLATE % (
        appengine_util.GetDefaultVersionHostname(), key)
    return result
