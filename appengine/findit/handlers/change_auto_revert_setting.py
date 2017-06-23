# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles requests to disable auto revert."""

import copy
import json

from google.appengine.api import users

from common import acl
from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler, Permission
from model import wf_config
from waterfall import waterfall_config


class ChangeAutoRevertSetting(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @token.AddXSRFToken(action_id='config')
  def HandleGet(self):
    auto_revert_on = waterfall_config.GetActionSettings().get(
        'revert_compile_culprit', False)
    return {
        'template': 'change_auto_revert_setting.html',
        'data': {
            'auto_revert_on': auto_revert_on
        }
    }

  @token.VerifyXSRFToken(action_id='config')
  def HandlePost(self):
    user = users.get_current_user()
    is_admin = users.IsCurrentUserAdmin()

    action_settings = copy.deepcopy(waterfall_config.GetActionSettings())
    revert_compile_culprit_on = json.loads(
        self.request.params.get('revert_compile_culprit'))
    if revert_compile_culprit_on:
      message = 'Enabling Auto Revert.'
    else:
      message = 'Disabling Auto Revert.'
    action_settings['revert_compile_culprit'] = revert_compile_culprit_on

    updated = wf_config.FinditConfig.Get().Update(
        user,
        acl.CanTriggerNewAnalysis(user.email(), is_admin),
        message=message,
        action_settings=action_settings)

    if not updated:
      return BaseHandler.CreateError(
          'Auto Revert setting is not changed. Please go back and try again.',
          501)

    return self.CreateRedirect('/waterfall/change-auto-revert-setting')
