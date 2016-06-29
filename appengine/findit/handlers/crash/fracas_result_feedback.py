# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import constants
from common import time_util
from common.base_handler import BaseHandler
from common.base_handler import Permission


class FracasResultFeedback(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):
    """Gets the analysis and feedback triage result of a crash.

    Serve HTML page or JSON result as requested.
    """
    key = self.request.get('key')

    analysis = ndb.Key(urlsafe=key).get()
    if not analysis:  # pragma: no cover.
      return BaseHandler.CreateError(
          'cannot find analysis for crash key %s' % key)

    data = {
        'signature': analysis.signature,
        'version': analysis.crashed_version,
        'channel': analysis.channel,
        'platform': analysis.platform,
        'regression_range': analysis.result.get('regression_range'),
        'historical_metadata': analysis.historical_metadata,
        'stack_trace': analysis.stack_trace,
        'suspected_cls': analysis.result.get('suspected_cls'),
        'suspected_project': analysis.result.get('suspected_project'),
        'suspected_components': analysis.result.get('suspected_components'),
        'request_time': time_util.FormatDatetime(analysis.requested_time),
        'analysis_completed': analysis.completed,
        'analysis_failed': analysis.failed,
    }

    return {
        'template': 'crash/fracas_result_feedback.html',
        'data': data,
    }
