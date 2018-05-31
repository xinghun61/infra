# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides a decorator to enhance message in exceptions.

  Decorate a function:
    @exceptions.EnhanceMessage
    def AProblematicFunction(a):
      return 1/0
"""

import functools
import os
import sys
import traceback


def EnhanceMessage(func):
  """Decorator to enhance the message of an exception in the new format.

  <file-name>:<line-number> <function-name> $$ <original-message>
  """

  @functools.wraps(func)
  def Wrapped(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except Exception as e:
      exc_type, _, exc_tb = sys.exc_info()

      stacks = traceback.extract_tb(exc_tb)
      if not stacks:  # pragma: no branch.
        raise  # No stack available, thus re-raise the original one.

      file_path = stacks[-1][0]
      # Only capture the file name and directories 2 levels up, as the full
      # file path won't help much. Use '/' to be consistent with unittests.
      file_path = '/'.join(file_path.split(os.sep)[-3:])
      line_num = stacks[-1][1]
      function_name = stacks[-1][2]

      new_message = '%s:%s %s $$ %s' % (file_path, line_num, function_name,
                                        e.message)
      # Re-raise the exception with the new message but the old traceback.
      raise exc_type, exc_type(new_message), exc_tb

  return Wrapped
