# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to handle manual triage of fracas crash analysis result."""

import json

from google.appengine.api import users
from google.appengine.ext import ndb

from common.base_handler import BaseHandler
from common.base_handler import Permission
from libs import time_util
from model import triage_status


@ndb.transactional
def _UpdateAnalysis(key, user_name, update_data):
  analysis = key.get()
  success = analysis.Update(update_data)

  result_property = None
  status = None
  for key, value in update_data.iteritems():
    if 'triage_status' in key:
      result_property = key.replace('_triage_status', '')
      status = value
      break

  if not result_property:
    analysis.put()
    return success

  triage_record = {
      'triage_timestamp': time_util.GetUTCNowTimestamp(),
      'user_name': user_name,
      'result_property': result_property,
      'triage_status': triage_status.TRIAGE_STATUS_TO_DESCRIPTION[status],
  }

  if not analysis.triage_history:
    analysis.triage_history = []

  analysis.triage_history.append(triage_record)

  analysis.put()
  return success


class TriageAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandlePost(self):
    """Sets the manual triage result for crash analysis."""
    key = ndb.Key(urlsafe=self.request.get('key'))
    update_data = self.request.params.get('update-data')
    if not update_data:
      return {'data': {'success': False}}

    update_data = json.loads(update_data)
    # As the permission level is CORP_USER, we could assume the current user
    # already logged in.
    user_name = users.get_current_user().email().split('@')[0]
    success = _UpdateAnalysis(key, user_name, update_data)

    return {'data': {'success': success}}
