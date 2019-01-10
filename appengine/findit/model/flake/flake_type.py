# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from protorpc import messages


class FlakeType(messages.Enum):
  """Enumerates types of flakes for FlakeOccurrence."""

  # A flaky test that caused a CL to be incorrectly rejected by CQ.
  # For how this type of flake occurrence is detected, please refer to:
  # services/flake_detection/flaky_tests.cq_false_rejection.sql.
  CQ_FALSE_REJECTION = 1

  # A flaky test that failed in the (with patch) steps, but passed in the
  # (retry with patch) steps.
  # For how this type of flake occurrence is detected, please refer to:
  # services/flake_detection/flaky_tests.retry_with_patch.sql.
  RETRY_WITH_PATCH = 2

  # A flaky test that failed some test runs then pass.
  CQ_HIDDEN_FLAKE = 3


FLAKE_TYPE_DESCRIPTIONS = {
    FlakeType.CQ_FALSE_REJECTION: 'cq false rejection',
    FlakeType.RETRY_WITH_PATCH: 'cq retry with patch',
    FlakeType.CQ_HIDDEN_FLAKE: 'cq hidden flake'
}

# Weights for each type of flakes.
# The weights are picked by intuitive, after comparing with other candidates.
# See goo.gl/y5awC5 for the comparison.
FLAKE_TYPE_WEIGHT = {
    FlakeType.CQ_FALSE_REJECTION: 100,
    FlakeType.RETRY_WITH_PATCH: 10,
    FlakeType.CQ_HIDDEN_FLAKE: 1
}
