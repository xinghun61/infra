# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An object representing an error in flake analysis."""

from libs.structured_object import StructuredObject


class FlakeAnalysisError(StructuredObject):
  """Represents an error in flake analysis."""
  # The error message to report.
  title = basestring

  # The likely root cause or other helpful information.
  description = basestring
