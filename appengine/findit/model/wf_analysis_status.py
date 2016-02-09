# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Represent status of the analysis of a Chromium waterfall build failure.
PENDING = 0
ANALYZING = 10
ANALYZED = 70
ERROR = 80
FLAKY = 100


STATUS_TO_DESCRIPTION = {
    PENDING: 'Pending',
    ANALYZING: 'Analyzing',
    ANALYZED: 'Analyzed',
    ERROR: 'Error'
}


TRY_JOB_STATUS_TO_DESCRIPTION = {
    PENDING: 'Pending',
    ANALYZING: 'Running',
    ANALYZED: 'Completed',
    ERROR: 'Error',
    FLAKY: 'Flaky'
}


SWARMING_TASK_STATUS_TO_DESCRIPTION = {
    PENDING: 'Pending',
    ANALYZING: 'Running',
    ANALYZED: 'Completed',
    ERROR: 'Error'
}
