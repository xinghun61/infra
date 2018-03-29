# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An object representing an error in a swarming task."""

from libs.structured_object import StructuredObject

# TODO(crbug.com/785463): Use enum for error codes.

# Swarming task stopped error codes.
BOT_DIED = 30
CANCELED = 40
EXPIRED = 50
TIMED_OUT = 60

STATES_NOT_RUNNING_TO_ERROR_CODES = {
    'BOT_DIED': BOT_DIED,
    'CANCELED': CANCELED,
    'EXPIRED': EXPIRED,
    'TIMED_OUT': TIMED_OUT,
}

# Customized error codes when getting results of a task.
# Outputs_ref is None.
NO_TASK_OUTPUTS = 300
# No files in isolate response.
# According to crbug/825419, this is not really a bug, but in this case, Findit
# cannot proceed, so save it as error.
NO_ISOLATED_FILES = 310
# Unable to retrieve output json.
NO_OUTPUT_JSON = 320
# Runner(pipeline) timed out.
RUNNER_TIMEOUT = 350
# Other/miscellaneous error codes.
UNKNOWN = 1000
# Unable to recognize the format of output json.
UNRECOGNIZABLE = 10

ERROR_CODE_TO_MESSAGE = {
    BOT_DIED: 'BOT_DIED',
    CANCELED: 'CANCELED',
    EXPIRED: 'EXPIRED',
    TIMED_OUT: 'TIMED_OUT',
    RUNNER_TIMEOUT: 'Runner to run swarming task timed out',
    NO_TASK_OUTPUTS: 'outputs_ref is None',
    NO_OUTPUT_JSON: 'No swarming task failure log',
    UNKNOWN: 'Unknown error',
    NO_ISOLATED_FILES: 'No files in isolated response',
    UNRECOGNIZABLE: 'Test results format is unrecognized, cannot find a parser.'
}


class SwarmingTaskError(StructuredObject):
  # The error code associated with the failure, which should correspond to
  #  defined in waterfall.swarming_util.
  code = int

  # The message associated with the error.
  message = basestring

  @classmethod
  def GenerateError(cls, code):
    return cls(
        code=code,
        message=ERROR_CODE_TO_MESSAGE.get(code, ERROR_CODE_TO_MESSAGE[UNKNOWN]))
