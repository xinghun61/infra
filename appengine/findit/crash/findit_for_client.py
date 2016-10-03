# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is interfacas between clients-specific code and core.

Note, fracas and cracas are almost identical and fracas is an intermidiate
state while transfering to cracas, so they can be handled in the same code path
and can be referred to as chromecrash."""

import copy
import json
import logging

from google.appengine.ext import ndb

from common import appengine_util
from common import time_util
from crash import findit_for_chromecrash
from crash.type_enums import CrashClient
from model import analysis_status
from model.crash.crash_config import CrashConfig
from model.crash.fracas_crash_analysis import FracasCrashAnalysis
from model.crash.cracas_crash_analysis import CracasCrashAnalysis

# TODO(katesonia): Move this to fracas config.
_FINDIT_FRACAS_FEEDBACK_URL_TEMPLATE = '%s/crash/fracas-result-feedback?key=%s'
# TODO(katesonia): Move this to a common config in config page.
_SUPPORTED_CLIENTS = [CrashClient.FRACAS, CrashClient.CRACAS]


def CheckPolicyForClient(crash_identifiers, chrome_version, signature,
                         client_id, platform, stack_trace, customized_data):
  """Checks if args pass client policy and updates parameters."""
  if client_id not in _SUPPORTED_CLIENTS:
    logging.info('Client %s is not supported by findit right now', client_id)
    return False, None

  config = CrashConfig.Get().GetClientConfig(client_id)
  # Cracas and Fracas share the sampe policy.
  if client_id == CrashClient.FRACAS or client_id == CrashClient.CRACAS:
    channel = customized_data.get('channel')
    # TODO(katesonia): Remove the default value after adding validity check to
    # config.
    if platform not in config.get(
        'supported_platform_list_by_channel', {}).get(channel, []):
      # Bail out if either the channel or platform is not supported yet.
      logging.info('Ananlysis of channel %s, platform %s is not supported. '
                   'No analysis is scheduled for %s',
                   channel, platform, repr(crash_identifiers))
      return False, None

    # TODO(katesonia): Remove the default value after adding validity check to
    # config.
    for blacklist_marker in config.get('signature_blacklist_markers', []):
      if blacklist_marker in signature:
        logging.info('%s signature is not supported. '
                     'No analysis is scheduled for %s', blacklist_marker,
                     repr(crash_identifiers))
        return False, None

    # TODO(katesonia): Remove the default value after adding validity check to
    # config.
    platform_rename = config.get('platform_rename', {})
    platform = platform_rename.get(platform, platform)

  elif client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
    # TODO(katesonia): Add clusterfuzz policy check.
    pass

  return True, (crash_identifiers, chrome_version, signature, client_id,
                platform, stack_trace, customized_data)


def GetAnalysisForClient(crash_identifiers, client_id):
  """Gets analysis entity based on client id."""
  if client_id == CrashClient.FRACAS:
    return FracasCrashAnalysis.Get(crash_identifiers)
  elif client_id == CrashClient.CRACAS:  # pragma: no cover.
    return CracasCrashAnalysis.Get(crash_identifiers)
  elif client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
    # TODO(katesonia): Add ClusterfuzzCrashAnalysis model.
    return None

  return None


def CreateAnalysisForClient(crash_identifiers, client_id):
  """Creates analysis entity based on client id."""
  if client_id == CrashClient.FRACAS:
    return FracasCrashAnalysis.Create(crash_identifiers)
  elif client_id == CrashClient.CRACAS:  # pragma: no cover.
    return CracasCrashAnalysis.Create(crash_identifiers)
  elif client_id == CrashClient.CLUSTERFUZZ: # pragma: no cover.
    # TODO(katesonia): define ClusterfuzzCrashAnalysis.
    return None

  return None


def ResetAnalysis(analysis, chrome_version, signature,
                  client_id, platform, stack_trace, customized_data):
  """Sets necessary info in the analysis for findit to run analysis."""
  analysis.Reset()

  # Set common properties.
  analysis.crashed_version = chrome_version
  analysis.stack_trace = stack_trace
  analysis.signature = signature
  analysis.platform = platform
  analysis.client_id = client_id

  if client_id == CrashClient.FRACAS or client_id == CrashClient.CRACAS:
    # Set customized properties.
    analysis.historical_metadata = customized_data.get('historical_metadata')
    analysis.channel = customized_data.get('channel')
  elif client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
    # TODO(katesonia): Set up clusterfuzz customized data.
    pass

  # Set analysis progress properties.
  analysis.status = analysis_status.PENDING
  analysis.requested_time = time_util.GetUTCNow()

  analysis.put()


def GetPublishResultFromAnalysis(analysis, crash_identifiers, client_id):
  """Gets result to be published to client from datastore analysis."""
  analysis_result = copy.deepcopy(analysis.result)

  if (analysis.client_id == CrashClient.FRACAS or
      analysis.client_id == CrashClient.CRACAS):
    analysis_result['feedback_url'] = _FINDIT_FRACAS_FEEDBACK_URL_TEMPLATE % (
        appengine_util.GetDefaultVersionHostname(), analysis.key.urlsafe())
    if analysis_result['found']:
      for cl in analysis_result['suspected_cls']:
        cl['confidence'] = round(cl['confidence'], 2)
        cl.pop('reason', None)
  elif client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
    # TODO(katesonia): Post process clusterfuzz analysis result if needed.
    pass

  return {
      'crash_identifiers': crash_identifiers,
      'client_id': analysis.client_id,
      'result': analysis_result,
  }


def FindCulprit(analysis):
  result = {'found': False}
  tags = {'found_suspects': False,
          'has_regression_range': False}

  if (analysis.client_id == CrashClient.FRACAS or
      analysis.client_id == CrashClient.CRACAS):
    result, tags = findit_for_chromecrash.FinditForChromeCrash().FindCulprit(
        analysis.signature, analysis.platform, analysis.stack_trace,
        analysis.crashed_version, analysis.historical_metadata)
  elif analysis.client_id == CrashClient.CLUSTERFUZZ:  # pragma: no cover.
    # TODO(katesonia): Implement findit_for_clusterfuzz.
    pass

  return result, tags
