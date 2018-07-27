# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from libs import analysis_status

INVALID_FAILURE_LOG = 'invalid'
FLAKY_FAILURE_LOG = 'flaky'
WRONG_FORMAT_LOG = 'not in desired test result formats'
TOO_LARGE_LOG = 'too large'

# Swarming task states.
STATE_PENDING = 'PENDING'
STATE_RUNNING = 'RUNNING'
STATE_COMPLETED = 'COMPLETED'
STATE_NOT_STOP = (STATE_PENDING, STATE_RUNNING)
STATE_NO_RESOURCE = 'NO_RESOURCE'

# The chromium git repository to pull revisions and blame info from.
CHROMIUM_GIT_REPOSITORY_URL = (
    'https://chromium.googlesource.com/chromium/src.git')
GITILES_HOST = 'chromium.googlesource.com'
GITILES_PROJECT = 'chromium/src'
GITILES_REF = 'refs/heads/master'

# Default limit hours to revert a culprit: should only revert a culprit if it's
# committed within this time range.
DEFAULT_CULPRIT_COMMIT_LIMIT_HOURS = 24

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

# Limit stored log data to 1000 KB, because a datastore entity has a size
# limit of 1 MB. And Leave 24 KB for other possible usage later.
# The stored log data in datastore will be compressed with gzip, backed by
# zlib. With the minimum compress level, the log data will usually be reduced
# to less than 20%. So for uncompressed data, a safe limit could be 4000 KB.
LOG_DATA_BYTE_LIMIT = 4000 * 1024
