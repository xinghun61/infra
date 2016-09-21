# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handles requests to the crash config page."""

import json

from google.appengine.api import users

from common.base_handler import BaseHandler
from common.base_handler import Permission
from model.crash.crash_config import CrashConfig as CrashConfigModel


class CrashConfig(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):
    settings = CrashConfigModel.Get()

    data = {
        'fracas': settings.fracas,
        'cracas': settings.cracas,
        'component_classifier': settings.component_classifier,
        'project_classifier': settings.project_classifier,
    }

    return {'template': 'crash/crash_config.html', 'data': data}

  def HandlePost(self):
    data = self.request.params.get('data')
    new_config_dict = json.loads(data)

    crash_config = CrashConfigModel.Get()

    crash_config.ClearCache()
    crash_config.Update(
        users.get_current_user(), users.IsCurrentUserAdmin(), **new_config_dict)
    return self.HandleGet()
