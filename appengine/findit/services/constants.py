# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from libs import analysis_status

INVALID_FAILURE_LOG = 'invalid'
FLAKY_FAILURE_LOG = 'flaky'
WRONG_FORMAT_LOG = 'not in desired test result formats'

# Swarming task states.
STATE_PENDING = 'PENDING'
STATE_RUNNING = 'RUNNING'
STATE_COMPLETED = 'COMPLETED'
STATE_NOT_STOP = (STATE_PENDING, STATE_RUNNING)

# Statuses for auto create a revert.
CREATED_BY_FINDIT = 0
CREATED_BY_SHERIFF = 1
ERROR = 2
SKIPPED = 3
COMMITTED = 4

AUTO_REVERT_STATUS_TO_ANALYSIS_STATUS = namedtuple(
    'status_map',
    'CREATED_BY_FINDIT CREATED_BY_SHERIFF ERROR SKIPPED COMMITTED')(
        analysis_status.COMPLETED, analysis_status.SKIPPED,
        analysis_status.ERROR, analysis_status.SKIPPED,
        analysis_status.COMPLETED)

CULPRIT_IS_A_REVERT = 'Culprit is a revert.'
AUTO_REVERT_OFF = 'Author of the culprit revision has turned off auto-revert.'
REVERTED_BY_SHERIFF = 'Culprit has been reverted by a sheriff or the CL owner.'
