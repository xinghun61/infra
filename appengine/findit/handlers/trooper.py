# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Handles requests to disable/enable certain features.

This handler is for troopers to turn off certain features when fire happens.
"""

import copy

from google.appengine.api import users

from common import acl
from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler, Permission
from model import wf_config
from waterfall import waterfall_config


class Trooper(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @token.AddXSRFToken(action_id='config')
  def HandleGet(self):
    action_settings = waterfall_config.GetActionSettings()
    auto_commit_revert_is_on = action_settings.get('auto_commit_revert', False)

    code_coverage_settings = waterfall_config.GetCodeCoverageSettings()
    code_coverage_is_on = (
        code_coverage_settings.get('serve_presubmit_coverage_data', False))

    return {
        'template': 'trooper.html',
        'data': {
            'is_admin': users.is_current_user_admin(),
            'auto_commit_revert_on': auto_commit_revert_is_on,
            'code_coverage_on': code_coverage_is_on,
        }
    }

  def _UpdateActionSettings(self, auto_commit_revert_is_on, user, message):
    """Updates the action settings.

    Args:
      auto_commit_revert_is_on (bool): Whether the auto commit revert feature is
                                       turned on.
      user: User who initiated the update.
      message: The update message.

    Returns:
      A bool indicates whether the update is successful.
    """
    action_settings = waterfall_config.GetActionSettings()
    if auto_commit_revert_is_on == action_settings.get('auto_commit_revert'):
      return False

    updated_action_settings = copy.deepcopy(action_settings)
    updated_action_settings['auto_commit_revert'] = auto_commit_revert_is_on
    return wf_config.FinditConfig.Get().Update(
        user,
        acl.IsPrivilegedUser(user.email(), users.is_current_user_admin()),
        message=message,
        action_settings=updated_action_settings)

  def _UpdateCodeCoverageSettings(self, code_coverage_is_on, user, message):
    """Updates the code coverage settings.

    Args:
      code_coverage_is_on (bool): Whether the code coverage feature is turned
                                  on.
      user: User who initiated the update.
      message: The update message.

    Returns:
      A bool indicates whether the update is successful.
    """
    code_coverage_settings = waterfall_config.GetCodeCoverageSettings()
    if code_coverage_is_on == code_coverage_settings.get(
        'serve_presubmit_coverage_data'):
      return False

    code_coverage_settings = copy.deepcopy(code_coverage_settings)
    code_coverage_settings[
        'serve_presubmit_coverage_data'] = code_coverage_is_on
    return wf_config.FinditConfig.Get().Update(
        user,
        acl.IsPrivilegedUser(user.email(), users.is_current_user_admin()),
        message=message,
        code_coverage_settings=code_coverage_settings)

  def _ParseValueOfButton(self, button_name):
    """Parses the value of the button.

    Args:
      button_name (str): Name of the button to check.

    Returns:
      True if the user wants to turn on the feature, False if the user wants to
      turn off the feature and None if the button is not clicked.
    """
    value = self.request.get(button_name, '').lower()
    if value == 'true':
      return True

    if value == 'false':
      return False

    return None

  @token.VerifyXSRFToken(action_id='config')
  def HandlePost(self):
    user = users.get_current_user()

    # Only admin could turn the features back on again.
    auto_commit_revert_is_turned_on = self._ParseValueOfButton(
        'auto_commit_revert')
    code_coverage_is_turned_on = self._ParseValueOfButton('code_coverage')
    if (auto_commit_revert_is_turned_on or
        code_coverage_is_turned_on) and not users.is_current_user_admin():
      return BaseHandler.CreateError('Only admin could turn features on.', 403)

    message = self.request.get('update_reason', '').strip()
    if not message:
      return BaseHandler.CreateError('Please enter the reason.', 400)

    assert ((auto_commit_revert_is_turned_on is not None) !=
            (code_coverage_is_turned_on is not None)
           ), 'One and only one button is expected to be clicked.'

    updated = False
    if auto_commit_revert_is_turned_on is not None:
      updated = self._UpdateActionSettings(auto_commit_revert_is_turned_on,
                                           user, message)
    else:
      updated = self._UpdateCodeCoverageSettings(code_coverage_is_turned_on,
                                                 user, message)

    if not updated:
      return BaseHandler.CreateError(
          'Failed to update settings. Please refresh the page and try again.',
          400)

    return self.CreateRedirect('/trooper')
