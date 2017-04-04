# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler, Permission
from handlers import handlers_util
from waterfall import buildbot


class SwarmingTask(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Get the information about swarming tasks for failed steps."""
    url = self.request.get('url').strip()
    build_keys = buildbot.ParseBuildUrl(url)

    if not build_keys:  # pragma: no cover
      return {'data': {}}

    data = handlers_util.GetSwarmingTaskInfo(*build_keys)
    return {'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
