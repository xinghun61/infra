# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INVALID_FAILURE_LOG = 'invalid'
FLAKY_FAILURE_LOG = 'flaky'
WRONG_FORMAT_LOG = 'not in desired test result formats'

# Swarming task states.
STATE_PENDING = 'PENDING'
STATE_RUNNING = 'RUNNING'
STATE_COMPLETED = 'COMPLETED'
STATE_NOT_STOP = (STATE_PENDING, STATE_RUNNING)
