# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An object representing an error in a swarming task."""

from libs.structured_object import StructuredObject


class SwarmingTaskError(StructuredObject):
  # The error code associated with the failure, which should correspond to
  #  defined in waterfall.swarming_util.
  code = int

  # The message associated with the error.
  message = basestring
