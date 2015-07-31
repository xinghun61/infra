# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to handle manual triage of analysis result.

This handler will flag the analysis result as correct or incorrect.
TODO: work on an automatic or semi-automatic way to triage analysis result.
"""

import calendar
from datetime import datetime

from google.appengine.api import users
from google.appengine.ext import ndb

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis import WfAnalysis
from model import wf_analysis_result_status
from waterfall import buildbot


@ndb.transactional
def _UpdateAnalysisResultStatus(
    master_name, builder_name, build_number, correct, user_name=None):
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis or not analysis.completed:
    return False

  if correct:
    if analysis.suspected_cls:
      analysis.result_status = wf_analysis_result_status.FOUND_CORRECT
      analysis.culprit_cls = analysis.suspected_cls
    else:
      analysis.result_status = wf_analysis_result_status.NOT_FOUND_CORRECT
      analysis.culprit_cls = None
  else:
    analysis.culprit_cls = None
    if analysis.suspected_cls:
      analysis.result_status = wf_analysis_result_status.FOUND_INCORRECT
    else:
      analysis.result_status = wf_analysis_result_status.NOT_FOUND_INCORRECT

  triage_record = {
      'triage_timestamp': calendar.timegm(datetime.utcnow().timetuple()),
      'user_name': user_name,
      'result_status': analysis.result_status,
      'version': analysis.version,
  }
  if not analysis.triage_history:
    analysis.triage_history = []
  analysis.triage_history.append(triage_record)

  analysis.put()
  return True


class TriageAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):  # pragma: no cover
    return self.HandlePost()

  def HandlePost(self):
    """Sets the manual triage result for the analysis.

    Mark the analysis result as correct/wrong/etc.
    TODO: make it possible to set the real culprit CLs.
    """
    url = self.request.get('url').strip()
    build_info = buildbot.ParseBuildUrl(url)
    if not build_info:
      return {'data': {'success': False}}
    master_name, builder_name, build_number = build_info

    correct = self.request.get('correct').lower() == 'true'
    # As the permission level is CORP_USER, we could assume the current user
    # already logged in.
    user_name = users.get_current_user().email().split('@')[0]
    success = _UpdateAnalysisResultStatus(
        master_name, builder_name, build_number, correct, user_name)
    return {'data': {'success': success}}
