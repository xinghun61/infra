# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configuration settings for Findit Waterfall."""

# TODO(lijeffrey): It is possible to configure findit using the appengine
# datastore, so future configuration changes would not necessarily require
# code changes.

# Maps masters by name to a list of corresponding unsupported step names.
UNSUPPORTED_STEPS = {
    'chromium.webkit': ['webkit_tests'],
}

def IsStepSupportedForMaster(step_name, master_name):  # pragma: no cover.
  """Determines whether or not a step is supported for the given build master.

  Args:
    step_name: The name of the step to check.
    master_name: The name of the build master to check.

  Returns:
    True if Findit supports analyzing the failure, False otherwise.
  """
  return step_name not in UNSUPPORTED_STEPS.get(master_name, [])