# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for actions on identified culprits for build failure.

It provides functions to:
  * Determine if Findit should take actions on a culprit
"""

import logging

from services import ci_failure


def ShouldTakeActionsOnCulprit(parameters):
  master_name, builder_name, build_number = parameters.build_key.GetParts()
  assert parameters.culprits

  if ci_failure.AnyNewBuildSucceeded(master_name, builder_name, build_number):
    # The builder has turned green, don't need to revert or send notification.
    logging.info('No revert or notification needed for culprit(s) for '
                 '%s/%s/%s since the builder has turned green.', master_name,
                 builder_name, build_number)
    return False

  return True
