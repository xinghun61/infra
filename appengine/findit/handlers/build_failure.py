# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import os

from google.appengine.api import users

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis_result_status import RESULT_STATUS_TO_DESCRIPTION
from waterfall import buildbot
from waterfall import build_failure_analysis_pipelines
from waterfall import masters


BUILD_FAILURE_ANALYSIS_TASKQUEUE = 'build-failure-analysis-queue'


def _FormatDatetime(dt):
  if not dt:
    return None
  else:
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def _GetTriageHistory(analysis):
  if (not users.is_current_user_admin() or
      not analysis.completed or
      not analysis.triage_history):
    return None

  triage_history = []
  for triage_record in analysis.triage_history:
    triage_history.append({
        'triage_time': _FormatDatetime(
            datetime.utcfromtimestamp(triage_record['triage_timestamp'])),
        'user_name': triage_record['user_name'],
        'result_status': RESULT_STATUS_TO_DESCRIPTION.get(
            triage_record['result_status']),
        'version': triage_record.get('version'),
    })

  return triage_history


class BuildFailure(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _ShowDebugInfo(self):
    # Show debug info only if the app is run locally during development, if the
    # currently logged-in user is an admin, or if it is explicitly requested
    # with parameter 'debug=1'.
    return (os.environ['SERVER_SOFTWARE'].startswith('Development') or
            users.is_current_user_admin() or self.request.get('debug') == '1')

  def _ShowTriageHelpButton(self):
    return users.is_current_user_admin()

  def HandleGet(self):
    """Triggers analysis of a build failure on demand and return current result.

    If the final analysis result is available, set cache-control to 1 day to
    avoid overload by unnecessary and frequent query from clients; otherwise
    set cache-control to 5 seconds to allow repeated query.

    Serve HTML page or JSON result as requested.
    """
    url = self.request.get('url').strip()
    build_info = buildbot.ParseBuildUrl(url)
    if not build_info:
      return BaseHandler.CreateError(
          'Url "%s" is not pointing to a build.' % url, 501)
    master_name, builder_name, build_number = build_info

    if not (masters.MasterIsSupported(master_name) or
            users.is_current_user_admin()):
      return BaseHandler.CreateError(
          'Master "%s" is not supported yet.' % master_name, 501)

    force = self.request.get('force') == '1'
    analysis = build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name, builder_name, build_number,
        force=force, queue_name=BUILD_FAILURE_ANALYSIS_TASKQUEUE)

    data = {
        'master_name': analysis.master_name,
        'builder_name': analysis.builder_name,
        'build_number': analysis.build_number,
        'pipeline_status_path': analysis.pipeline_status_path,
        'show_debug_info': self._ShowDebugInfo(),
        'analysis_request_time': _FormatDatetime(analysis.request_time),
        'analysis_start_time': _FormatDatetime(analysis.start_time),
        'analysis_end_time': _FormatDatetime(analysis.end_time),
        'analysis_duration': analysis.duration,
        'analysis_update_time': _FormatDatetime(analysis.updated_time),
        'analysis_completed': analysis.completed,
        'analysis_failed': analysis.failed,
        'analysis_result': analysis.result,
        'analysis_correct': analysis.correct,
        'triage_history': _GetTriageHistory(analysis),
        'show_triage_help_button': self._ShowTriageHelpButton(),
    }

    return {'template': 'build_failure.html', 'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
