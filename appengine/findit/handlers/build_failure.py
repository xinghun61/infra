# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission


class BuildFailure(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):  #pylint: disable=R0201
    """Trigger analysis of a build failure on demand and return current result.

    If the final analysis result is available, set cache-control to 1 day to
    avoid overload by unnecessary and frequent query from clients; otherwise
    set cache-control to 5 seconds to allow recursive query.

    Serve HTML page or JSON result as requested.
    """
    return BaseHandler.CreateError('Not implemented yet!', 501)

  def HandlePost(self):  #pylint: disable=R0201
    return self.HandleGet()
