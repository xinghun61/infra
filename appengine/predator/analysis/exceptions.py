# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class PredatorError(Exception):
  """Base class for Predator-specific exceptions."""

  pass


class FailedToParseStacktrace(PredatorError):  # pragma: no cover.
  """Base class for Predator-specific exceptions."""

  def __init__(self, message):
    super(FailedToParseStacktrace, self).__init__(message)

  @property
  def name(self):
    return 'Failed to parse stackrace'
