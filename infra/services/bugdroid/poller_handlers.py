# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Collection of standard handlers for repository pollers."""


class BasePollerHandler(object):
  """Default Poller Handler configuration.

  Args:
    must_succeed: When set, in order for a log entry to be considered properly
      processed, ProcessLogEntry() must finish successfully for this handler.
  """

  def __init__(self, must_succeed=False):
    self.must_succeed = must_succeed
    # This is set when the handler is added to the poller (unless there is no
    # logger set on the poller).
    self.logger = None

  def WarmUp(self):
    pass

  def ProcessLogEntry(self, log_entry):
    pass