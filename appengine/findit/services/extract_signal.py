# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for extracting failure signals.

It provides helper functions and common logic to extract failure signals.
"""

import logging

from google.appengine.api.urlfetch import ResponseTooLargeError

from model.wf_analysis import WfAnalysis
from services.constants import LOG_DATA_BYTE_LIMIT
from services import step_util


class FailedToGetFailureLogError(Exception):
  pass


def ExtractStorablePortionOfLog(log_data, json_format=False):
  # For the log of a failed step in a build, the error messages usually show
  # up at the end of the whole log. So if the log is too big to fit into a
  # datastore entity, it's safe to just save the ending portion of the log.
  if len(log_data) <= LOG_DATA_BYTE_LIMIT:
    return log_data
  if json_format:
    # TODO (crbug/806406): Parse and save useful log in json_formatted logs.
    return ''

  lines = log_data.split('\n')
  size = 0
  for line_index in reversed(range(len(lines))):
    size += len(lines[line_index]) + 1
    if size > LOG_DATA_BYTE_LIMIT:
      return '\n'.join(lines[line_index + 1:])
  else:
    return log_data  # pragma: no cover - this won't be reached.


def GetStdoutLog(master_name, builder_name, build_number, step_name,
                 http_client):
  try:
    return step_util.GetWaterfallBuildStepLog(
        master_name, builder_name, build_number, step_name, http_client)

  except ResponseTooLargeError:
    logging.exception('Log of step "%s" is too large for urlfetch.', step_name)
    # If the stdio log of a step is too large, we don't want to pull
    # it again in next run, because that might lead to DDoS to the
    # master.
    return 'Stdio log is too large for urlfetch.'


def SaveSignalInAnalysis(master_name, builder_name, build_number, signals):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.signals = signals
  analysis.put()
