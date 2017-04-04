# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.api import users
from google.appengine.ext import ndb

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util


def _GetTriageHistory(analysis):
  if (not users.is_current_user_admin() or
      not analysis.completed or
      not analysis.triage_history):
    return None

  triage_history = []
  for triage_record in analysis.triage_history:
    triage_history.append({
        'triage_time': time_util.FormatDatetime(
            datetime.utcfromtimestamp(triage_record['triage_timestamp'])),
        'result_property': triage_record['result_property'],
        'user_name': triage_record['user_name'],
        'triage_status': triage_record['triage_status']
    })

  return triage_history


class ResultFeedback(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @property
  def client(self):
    raise NotImplementedError()

  def HandleGet(self):
    """Gets the analysis and feedback triage result of a crash.

    Serve HTML page or JSON result as requested.
    """
    key = self.request.get('key')

    analysis = ndb.Key(urlsafe=key).get()
    if not analysis:  # pragma: no cover.
      return BaseHandler.CreateError(
          'cannot find analysis for crash key %s' % key)

    if analysis.stack_trace:
      # Old crash analysis stored raw stacktrace string instead of the parsed
      # stacktrace.
      stacktrace_str = analysis.stack_trace
    else:
      stack_strs = []
      for stack in analysis.stacktrace.stacks if analysis.stacktrace else []:
        stack_strs.append('\n'.join([str(frame) for frame in stack.frames]))
      stacktrace_str = '\n'.join(stack_strs)

    # Legacy culprit cls is a list of Suspect.ToDict(), new data is just a list
    # of commit urls.
    culprit_cls = None
    if analysis.culprit_cls:
      culprit_cls = [(cl if isinstance(cl, basestring) else cl['url'])
                     for cl in analysis.culprit_cls]

    data = {
        'client': self.client,
        'crash_url': analysis.crash_url,
        'signature': analysis.signature,
        'version': analysis.crashed_version,
        'platform': analysis.platform,
        'regression_range': analysis.result.get(
            'regression_range') if analysis.result else None,
        'culprit_regression_range': analysis.culprit_regression_range,
        'stack_trace': stacktrace_str,
        'suspected_cls': analysis.result.get(
            'suspected_cls') if analysis.result else None ,
        'culprit_cls': culprit_cls,
        'suspected_project': analysis.result.get(
            'suspected_project') if analysis.result else None,
        'culprit_project': analysis.culprit_project,
        'suspected_components': analysis.result.get(
            'suspected_components') if analysis.result else None,
        'culprit_components': analysis.culprit_components,
        'request_time': time_util.FormatDatetime(analysis.requested_time),
        'analysis_completed': analysis.completed,
        'analysis_failed': analysis.failed,
        'triage_history': _GetTriageHistory(analysis),
        'analysis_correct': {
            'regression_range': analysis.regression_range_triage_status,
            'suspected_cls': analysis.suspected_cls_triage_status,
            'suspected_project': analysis.suspected_project_triage_status,
            'suspected_components': analysis.suspected_components_triage_status,
        },
        'note': analysis.note,
        'key': analysis.key.urlsafe(),
    }

    data.update(analysis.customized_data)

    return {
        'template': 'crash/result_feedback.html',
        'data': data,
    }
