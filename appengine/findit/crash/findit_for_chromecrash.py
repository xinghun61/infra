# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from crash import detect_regression_range
from crash.changelist_classifier import ChangelistClassifier
from crash.chromecrash_parser import ChromeCrashParser
from crash.component_classifier import Component
from crash.component_classifier import ComponentClassifier
from crash.findit import Findit
from crash.predator import Predator
from crash.project_classifier import ProjectClassifier
from crash.type_enums import CrashClient
from model.crash.cracas_crash_analysis import CracasCrashAnalysis
from model.crash.crash_config import CrashConfig
from model.crash.fracas_crash_analysis import FracasCrashAnalysis

# TODO(katesonia): Remove the default value after adding validity check to
# config.
_DEFAULT_TOP_N = 7


# TODO(wrengr): [Note#1] in many places below we have to do some ugly
# defaulting in case crash_data is missing certain keys. If we had
# crash_data be a proper class, rather than an anonymous dict, then we
# could clean all this up by having the properties themselves do the check
# and return the default whenever keys are missing. This would also
# let us do things like have regression_range be automatically computed
# from historical_metadata (when historical_metadata is provided and
# regression_range is not).

class FinditForChromeCrash(Findit):
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

  # TODO(http://crbug.com/659354): remove the dependency on CrashConfig
  # entirely, by passing the relevant data as arguments to this constructor.
  def __init__(self, repository, pipeline_cls):
    super(FinditForChromeCrash, self).__init__(repository, pipeline_cls)
    component_classifier_config = CrashConfig.Get().component_classifier

    self._stacktrace_parser = ChromeCrashParser()

    # For how these two "top n" differ, see http://crbug.com/644476#c4
    self._predator = Predator(
        cl_classifier = ChangelistClassifier(
            repository = repository,
            top_n_frames = self.config.get('top_n', _DEFAULT_TOP_N)),
        component_classifier = ComponentClassifier(
            [Component(component_name, path_regex, function_regex)
            for path_regex, function_regex, component_name
            in component_classifier_config['path_function_component']],
            component_classifier_config['top_n']),
        project_classifier = ProjectClassifier())

  def _InitializeAnalysis(self, model, crash_data):
    super(FinditForChromeCrash, self)._InitializeAnalysis(model, crash_data)
    # TODO(wrengr): see Note#1
    customized_data = crash_data.get('customized_data', {})
    model.channel = customized_data.get('channel', None)
    model.historical_metadata = customized_data.get('historical_metadata', [])

  # TODO(wrengr): see Note#1, which would allow us to lift this
  # implementation to the Findit base class.
  @ndb.transactional
  def _NeedsNewAnalysis(self, crash_data):
    crash_identifiers = crash_data['crash_identifiers']
    historical_metadata = crash_data['customized_data']['historical_metadata']
    model = self.GetAnalysis(crash_identifiers)
    # N.B., for mocking reasons, we must not call DetectRegressionRange
    # directly, but rather must access it indirectly through the module.
    new_regression_range = detect_regression_range.DetectRegressionRange(
        historical_metadata)
    if (model and not model.failed and
        new_regression_range == model.regression_range):
      logging.info('The analysis of %s has already been done.',
                   repr(crash_identifiers))
      return False

    if not model:
      model = self.CreateAnalysis(crash_identifiers)

    crash_data['regression_range'] = new_regression_range
    self._InitializeAnalysis(model, crash_data)
    model.put()
    return True

  def CheckPolicy(self, crash_data):
    crash_identifiers = crash_data['crash_identifiers']
    platform = crash_data['platform']
    # TODO(wrengr): see Note#1
    channel = crash_data.get('customized_data', {}).get('channel', None)
    # TODO(katesonia): Remove the default value after adding validity check to
    # config.
    if platform not in self.config.get(
        'supported_platform_list_by_channel', {}).get(channel, []):
      # Bail out if either the channel or platform is not supported yet.
      logging.info('Analysis of channel %s, platform %s is not supported. '
                   'No analysis is scheduled for %s',
                   channel, platform, repr(crash_identifiers))
      return None

    signature = crash_data['signature']
    # TODO(wrengr): can this blacklist stuff be lifted to the base class?
    # TODO(katesonia): Remove the default value after adding validity check to
    # config.
    for blacklist_marker in self.config.get('signature_blacklist_markers', []):
      if blacklist_marker in signature:
        logging.info('%s signature is not supported. '
                     'No analysis is scheduled for %s', blacklist_marker,
                     repr(crash_identifiers))
        return None

    # TODO(wrengr): should we clone |crash_data| rather than mutating it?
    crash_data['platform'] = self.RenamePlatform(platform)
    return crash_data


# TODO(http://crbug.com/659346): we misplaced the coverage tests; find them!
class FinditForCracas(FinditForChromeCrash): # pragma: no cover
  @classmethod
  def _ClientID(cls):
    return CrashClient.CRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Create stuff here.
    return CracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Get stuff here.
    return CracasCrashAnalysis.Get(crash_identifiers)


class FinditForFracas(FinditForChromeCrash):
  @classmethod
  def _ClientID(cls):
    return CrashClient.FRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Create stuff here.
    return FracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Get stuff here.
    return FracasCrashAnalysis.Get(crash_identifiers)
