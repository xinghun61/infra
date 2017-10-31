# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
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
from gae_libs import pubsub_util


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
         TouchCrashedDirectoryFeature(options=config.feature_options[
             'TouchCrashedDirectory']),
         TouchCrashedComponentFeature(
             self._component_classifier,
             options=config.feature_options['TouchCrashedComponent'])])

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
    return ClusterfuzzData(raw_crash_data, self._get_repository,
                           top_n_frames=self.client_config['top_n'])

  def ResultMessageToClient(self, analysis):
    """Converts culprit into publishable result to client.

    Args:
      analysis (ClusterfuzzAnalysis): The ClusterfuzzAnalysis entity which
          contains the result.

    Returns:
      A dict of the given ``crash_identifiers``, this model's
      ``client_id``, and a publishable version of this model's ``result``.
    """
    result = copy.deepcopy(analysis.result)
    result['feedback_url'] = analysis.feedback_url
    if 'regression_range' in result:
      del result['regression_range']

    return {
        'crash_identifiers': analysis.identifiers,
        'client_id': self.client_id,
        'result': result
    }

  def MessageToTryBot(self, analysis):
    """Gets log to push to try bot topic."""
    regression_ranges = []
    dep_rolls = (analysis.dependency_rolls.itervalues()
                 if analysis.dependency_rolls else [])
    for dep_roll in dep_rolls:
      repository = self._get_repository(dep_roll.repo_url)
      regression_range = dep_roll.ToDict()
      regression_range.update(
          {'commits': repository.GetCommitsBetweenRevisions(
              dep_roll.old_revision, dep_roll.new_revision)})
      regression_ranges.append(regression_range)

    message = {
        'regression_ranges': regression_ranges,
        'testcase_id': analysis.testcase_id,
        'feedback_url': analysis.feedback_url,
    }
    if 'suspected_cls' in analysis.result:
      message['suspected_cls'] = analysis.result['suspected_cls']

    return message

  def PublishResultToTryBot(self, analysis):
    """Publishes heuristic results to try bot."""
    message = self.MessageToTryBot(analysis)
    topic = self.client_config['try_bot_topic']
    pubsub_util.PublishMessagesToTopic([json.dumps(message)], topic)
    logging.info('Publish result for %s to try-bot %s:\n%s',
                 repr(analysis.identifiers), topic,
                 json.dumps(message, sort_keys=True, indent=4))

  def PublishResult(self, crash_identifiers):
    """Publish results to clusterfuzz and try bot."""
    analysis = self.GetAnalysis(crash_identifiers)
    if not analysis or analysis.failed:
      logging.info('Can\'t publish results because analysis failed: %s',
                   repr(crash_identifiers))
      return

    self.PublishResultToClient(analysis)

    supported_platforms = self.client_config['try_bot_supported_platforms']
    if not analysis.platform in supported_platforms:
      logging.info('Skipping testcase because %s is not a supported platform.'
                   ' Supported platforms: %s.', analysis.platform,
                   repr(supported_platforms))
      return

    self.PublishResultToTryBot(analysis)
