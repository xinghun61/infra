# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Constants used for flake analysis."""
# Used to calculate the time between retries when we try the analysis
# during off-peak hours.
BASE_COUNT_DOWN_SECONDS = 2 * 60

# Max build numbers to look back during a build-level analysis.
DEFAULT_MAX_BUILD_NUMBERS = 500

# Default iterations to rerun if our config is empty.
DEFAULT_SWARMING_TASK_ITERATIONS_TO_RERUN = 100

# Tries to start the RecursiveFlakePipeline on peak hours at most 5 times.
MAX_RETRY_TIMES = 5

# In order not to hog resources on the swarming server, set the timeout to a
# non-configurable 3 hours.
MAX_TIMEOUT_SECONDS = 3 * 60 * 60

ONE_HOUR_IN_SECONDS = 60 * 60

# Value to indicate a test does not exist at a build number or commit position.
PASS_RATE_TEST_NOT_FOUND = -1