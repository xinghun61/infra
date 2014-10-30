# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.findit.base_handler import BaseHandler
from appengine_module.findit.base_handler import Permission


class AnalyzeBuildFailure(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):  #pylint: disable=R0201
    """Do the actual analysis of a build failure.

    It's for internal task queue requests, and not for access by end users.
    """
    return BaseHandler.CreateError('Not implemented yet!', 501)
