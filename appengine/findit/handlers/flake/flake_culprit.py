# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util


def _ConvertAnalysisToDict(analysis_urlsafe_key):
  """Returns a dict representation of a flake analysis.

  Args:
    analysis_urlsafe_key (str): The urlsafe key of a MasterFlakeAnalysis

  Returns:
    A dict representation of the analysis for display purposes.
  """
  analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
  assert analysis
  return {
      'builder_name': analysis.builder_name,
      'confidence_in_culprit': analysis.confidence_in_culprit,
      'key': analysis_urlsafe_key,
      'master_name': analysis.master_name,
      'step_name': analysis.step_name,
      'test_name': analysis.test_name,
  }


def _GetFlakeAnalysesAsDicts(culprit):
  """Returns a list of dicts of analyses associated with a flake culprit."""
  return map(_ConvertAnalysisToDict, culprit.flake_analysis_urlsafe_keys)


class FlakeCulprit(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Lists the flake analyses in which the culprit introduced flakiness."""
    key = self.request.get('key', '')

    culprit = ndb.Key(urlsafe=key).get()
    if not culprit:
      return BaseHandler.CreateError('Culprit not found!', 404)

    data = {
        'project_name':
            culprit.project_name,
        'revision':
            culprit.revision,
        'commit_position':
            culprit.commit_position,
        'cr_notified':
            culprit.cr_notified,
        'cr_notification_time':
            time_util.FormatDatetime(culprit.cr_notification_time),
        'analyses':
            _GetFlakeAnalysesAsDicts(culprit),
        'key':
            key,
    }

    return {'template': 'flake/flake-culprit.html', 'data': data}
