# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission


class ReadEntity(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  def HandleGet(self):  #pylint: disable=R0201
    """Shows properties of arbitrary ndb entity as a JSON result.

    This is a debating HTTP endpoint.
    It is more for debugging, because some entity properties (like stdio,
    CL diff) are too large and saved in compressed mode, so that they are not
    human readable in the appengine admin console.
    """
    return BaseHandler.CreateError('Not implemented yet!', 501)
