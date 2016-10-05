# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def ScheduleAnalysisForFlake(
    _request, _user_email, _is_admin):  # pragma: no cover.
  """Schedules an analysis on the flake in the given request if needed.

  Args:
    request (FlakeAnalysisRequest): The request to analyze a flake.
    user_email (str): The email of the requester.
    is_admin (bool): Whether the requester is an admin.

  Returns:
    An instance of MasterFlakeAnalysis if an analysis was scheduled; otherwise
    None if no analysis was scheduled before and the user has no permission to.
  """
  # TODO (stgao): hook up with analysis.
  return False
