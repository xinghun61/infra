# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Constants used for flake analysis."""

# Alpha for statistical analysis. A 95% confidence interval would have alpha
# value 0.05. An alpha value of 0.001 means 99.9% confidence.
ALPHA = 0.001

# Used to calculate the time between retries when we try the analysis
# during off-peak hours.
BASE_COUNT_DOWN_SECONDS = 2 * 60

# The Chromium project name.
CHROMIUM_PROJECT_NAME = 'chromium'

# Percent to consider when sampling that a pass rate has converged.
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
DEFAULT_LOWER_FLAKE_THRESHOLD = 1e-7

# Number of bugs for flaky tests allowed to be filed per day.
DEFAULT_MAX_BUG_UPDATES_PER_DAY = 30

# Number of commit positions to look back. Flakiness is most relevant within
# roughly 500 build cycles from when it's detected, and each build has roughly
# 10 commits.
# TODO(crbug.com/799383): Add to config.
DEFAULT_MAX_COMMIT_POSITIONS_TO_LOOK_BACK = 500 * 10  # 5000 commits.

# Max build numbers to look back during a build-level analysis.
DEFAULT_MAX_BUILD_NUMBERS = 500

# Maximum number of times to rerun at a certain build number.
DEFAULT_MAX_ITERATIONS_TO_RERUN = 400

# Maximum number of times a swarming task can be retried for the same data
# point.
DEFAULT_MAX_SWARMING_TASK_RETRIES_PER_DATA_POINT = 3

# Minimum number of occurrences of a flaky test that are associated with
# different CLs within the past 24h are required in order to report the flake.
# Note that it has to be x different CLs, different patchsets of the same CL are
# only counted once, and the reason is to filter out flaky tests that are caused
# by a specific uncommitted CL.
DEFAULT_MINIMUM_REQUIRED_IMPACTED_CLS_PER_DAY = 3

# Default required ci occurrence count in past 24 hours to report the bug.
DEFAULT_MINIMUM_REQUIRED_CI_OCCURRENCES_PER_DAY = 3

# Default minimum confidence score to post notifications to code reviews.
DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_ENDPOINTS = 0.7

# Default number of bots on swarming needed to trigger tasks immediately.
DEFAULT_MINIMUM_NUMBER_AVAILABLE_BOTS = 5

# Default minimum percentag of bots on swarming available to trigger tasks.
DEFAULT_MINIMUM_PERCENTAGE_AVAILABLE_BOTS = 0.1

# Default iterations to rerun if our config is empty.
DEFAULT_SWARMING_TASK_ITERATIONS_TO_RERUN = 100

# Default swarming task length, one hour.
DEFAULT_TIMEOUT_PER_SWARMING_TASK_SECONDS = 60 * 60

# Default test length, two minutes.
DEFAULT_TIMEOUT_PER_TEST_SECONDS = 120

# The minimum pass rate of a data point to be considered stable and passing.
DEFAULT_UPPER_FLAKE_THRESHOLD = 0.9999999

# Epsilon for floating point comparison.
EPSILON = 0.001

# This suffix distinguishes the on-bot named cache (work directory) from flake
# vs. non-flake tryjobs.
FLAKE_CACHE_SUFFIX = 'flake'

# Maximum iterations allowed per swarming task.
MAX_ITERATIONS_PER_TASK = 200

# Tries to start the RecursiveFlakePipeline on peak hours at most 5 times.
MAX_RETRY_TIMES = 5

# The maximum number of swarming task retries we can retry per build.
MAX_SWARMING_TASK_RETRIES_PER_BUILD = 2

# In order not to hog resources on the swarming server, set the timeout to a
# non-configurable 3 hours.
MAX_TIMEOUT_SECONDS = 3 * 60 * 60

# The minimum number of iterations to be run before convergance is considered.
# All variables related to convergence aren't configurable right now since it
# should be a constant.
MINIMUM_ITERATIONS_REQUIRED_FOR_CONVERGENCE = 400

# Value to indicate a test does not exist at a build number or commit position.
PASS_RATE_TEST_NOT_FOUND = -1.0

# The minimum required number of fully-stable points before a culprit in order
# to send a notification to the code review. Statistically, 2 should be high
# probability that the stable points are indeed stable. For example, assume a
# test has a uniform 0.98 chance of passing, which is considered stable, and a
# 100 iteration requirement for confidence. Then the probability of a
# fully-stable data point being generated is 0.98^100 = 0.133, meaning there is
# a 13.3% chance the stable point is false. For two such points to exist
# consecutively would be 0.133^2, or 1.8%, 3 such points would be 0.03%, etc.
REQUIRED_NUMBER_OF_STABLE_POINTS_BEFORE_CULPRIT = 2

# Cushion multiplier for test setup/teardown.
SWARMING_TASK_CUSHION_MULTIPLIER = 2.0

# List of unsupported masters for running try jobs.
UNSUPPORTED_MASTERS_FOR_TRY_JOBS = ['chromium.sandbox']
