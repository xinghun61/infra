# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Constants used for flake analysis."""
# Used to calculate the time between retries when we try the analysis
# during off-peak hours.
BASE_COUNT_DOWN_SECONDS = 2 * 60

# Percent that when sampling we consider that the pass rate has converged.
# This means that if pass_rate_a - pass_rate_b < this that the test has
# reached its pass rate.
CONVERGENCE_PERCENT = .05  # 5 percent.

# Sample size to find out the average test length.
DEFAULT_DATA_POINT_SAMPLE_SIZE = 5

# Number of iterations executed per swarming task. This is derived
# through the default length for a swarming task being one our
# and the default length of a test being two minutes.
DEFAULT_ITERATIONS_PER_TASK = 35

# Static number of iterations to run to be reasonably confident that the
# task will complete. To be used on the run after a timeout occurs.
DEFAULT_ITERATIONS_TO_RUN_AFTER_TIMEOUT = 10

# The maximum pass rate of a data point to be considered stable and failing.
DEFAULT_LOWER_FLAKE_THRESHOLD = 0.02

# Max build numbers to look back during a build-level analysis.
DEFAULT_MAX_BUILD_NUMBERS = 500

# Maximum number of times to rerun at a certain build number.
DEFAULT_MAX_ITERATIONS_TO_RERUN = 400

# Default minimum confidence score to run try jobs.
DEFAULT_MINIMUM_CONFIDENCE_SCORE = 0.6

# Default minimum confidence score to post notifications to code reviews.
DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR = 0.7

# Default iterations to rerun if our config is empty.
DEFAULT_SWARMING_TASK_ITERATIONS_TO_RERUN = 100

# Default swarming task length, one hour.
DEFAULT_TIMEOUT_PER_SWARMING_TASK_SECONDS = 60 * 60

# Default test length, two minutes.
DEFAULT_TIMEOUT_PER_TEST_SECONDS = 120

# The minimum pass rate of a data point to be considered stable and passing.
DEFAULT_UPPER_FLAKE_THRESHOLD = 0.98

# Epsilon for floating point comparison.
EPSILON = 0.001

# Maximum iterations allowed per swarming task.
MAX_ITERATIONS_PER_TASK = 200

# Tries to start the RecursiveFlakePipeline on peak hours at most 5 times.
MAX_RETRY_TIMES = 5

# The maximum number of swarming task retries we can retry per build.
MAX_SWARMING_TASK_RETRIES_PER_BUILD = 2

# In order not to hog resources on the swarming server, set the timeout to a
# non-configurable 3 hours.
MAX_TIMEOUT_SECONDS = 3 * 60 * 60

# The minimum confidence required to create a bug.
MINIMUM_CONFIDENCE_TO_CREATE_BUG = 1.0

# The minimum number of iterations to be run before convergance is considered.
# All variables related to convergence aren't configurable right now since it
# should be a constant.
MINIMUM_ITERATIONS_REQUIRED_FOR_CONVERGENCE = 100

# Value to indicate a test does not exist at a build number or commit position.
PASS_RATE_TEST_NOT_FOUND = -1

# The minimum required number of fully-stable points before a culprit in order
# to send a notification to the code review. Based on historical data 3 stable
# points should be able to weed out most false positives, and should not be
# configurable.
REQUIRED_NUMBER_OF_STABLE_POINTS_BEFORE_CULPRIT = 3

# Cushion multiplier for test setup/teardown.
SWARMING_TASK_CUSHION_MULTIPLIER = 2.0
