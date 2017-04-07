# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Represent status of the analysis of a Chromium waterfall compile/test failure
# or a Chrome crash.
PENDING = 0
RUNNING = 10
COMPLETED = 70
ERROR = 80
SKIPPED = 100


STATUS_TO_DESCRIPTION = {
    PENDING: 'Pending',
    RUNNING: 'Running',
    COMPLETED: 'Completed',
    ERROR: 'Error',
    SKIPPED: 'Skipped',
}
