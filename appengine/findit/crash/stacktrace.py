# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Stacktrace(list):
  """Interface Represents Stacktrace object.

  Contains a list of callstacks, because one stacktrace may have more than
  one callstacks."""
  def __init__(self):
    super(Stacktrace, self).__init__()

  def GetCrashStack(self):
    """Gets the crash stack with the highest (lowest number) priority in
    stacktrace."""
    if not self:
      return None

    # Return the first stack with the least priority. The smaller the number,
    # the higher the priority beginning with 0.
    return sorted(self, key=lambda stack: stack.priority)[0]
