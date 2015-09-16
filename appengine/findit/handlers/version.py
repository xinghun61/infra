# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import modules

from base_handler import BaseHandler
from base_handler import Permission


class Version(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Responses the deployed version of this app."""
    self.response.write(modules.get_current_version_name())
