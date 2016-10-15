# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to handle manual triage of a suspected flake result.

This handler will mark the suspected flake result as correct or incorrect.
"""

from google.appengine.api import users

from common.base_handler import BaseHandler
from common.base_handler import Permission
from model.flake.master_flake_analysis import MasterFlakeAnalysis


def _UpdateSuspectedFlakeAnalysis(
    master_name, builder_name, build_number, step_name, test_name,
    version_number, suspected_build_number, triage_result, user_name):
  master_flake_analysis = MasterFlakeAnalysis.GetVersion(
      master_name, builder_name, build_number, step_name, test_name,
      version_number)

  if not master_flake_analysis:  # pragma: no cover
    return False

  suspect_info = {
      'build_number': suspected_build_number
  }

  master_flake_analysis.UpdateTriageResult(
      triage_result, suspect_info, user_name, version_number)
  master_flake_analysis.put()
  return True


class TriageFlakeAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):  # pragma: no cover
    """Sets the manual triage result for the suspected flake analysis."""
    flake_info = self.request.get('flake_info')
    (master_name, builder_name, build_number, step_name, test_name,
     version_number, suspected_build_number) = flake_info.split('/')
    triage_result = self.request.get('triage_result')

    if not (master_name and builder_name and build_number and step_name and
            test_name and version_number and suspected_build_number and
            str(triage_result)):
      # All fields needed for getting master_flake_analysis must be provided in
      # order to update triage results.
      return {'data': {'success': False}}

    # As the permission level is CORP_USER, we could assume the current user
    # already logged in.
    user_name = users.get_current_user().email().split('@')[0]

    success = _UpdateSuspectedFlakeAnalysis(
        master_name, builder_name, build_number, step_name, test_name,
        int(version_number), suspected_build_number, int(triage_result),
        user_name)

    return {'data': {'success': success}}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
