# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.base_handler import BaseHandler, Permission
from gae_libs import appengine_util


class Version(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Responses the deployed version of this app."""
    self.response.write(appengine_util.GetCurrentVersion())
