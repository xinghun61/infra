# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for actions on identified culprits for compile failure.

It provides functions to:
  * Determine if Findit should take actions on a culprit
"""

from services import culprit_action

_BYPASS_MASTER_NAME = 'chromium.sandbox'


def ShouldTakeActionsOnCulprit(parameters):
  if parameters.build_key.master_name == _BYPASS_MASTER_NAME:
    # This is a hack to prevent Findit taking any actions on
    # master.chromium.sandbox.
    # TODO(crbug/772972): remove this check for special master name after it
    # is removed. If no special check remained for compile, this file can be
    # removed as well.
    return False

  return culprit_action.ShouldTakeActionsOnCulprit(parameters)
