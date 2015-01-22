# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission


class TriageAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandlePost(self):  #pylint: disable=R0201
    """Sets the manual triage result for the analysis.

    Update the culprit CLs and mark the analysis result as correct/wrong/etc.
    This corresponds to the "Update" button in following page:
    https://findit-for-me.appspot.com/list-build?count=400&type=triage
    """
    return BaseHandler.CreateError('Not implemented yet!', 501)
