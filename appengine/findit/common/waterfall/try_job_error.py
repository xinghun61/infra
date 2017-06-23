# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Represents possible error codes for what can go wrong during try jobs."""

# An error was detected but the root cause unknown. Cases resulting in this
# should be investigated individually and common root causes added to this
# module as dedicated error codes.
UNKNOWN = 10
# The try job did not finish within the required time and was abandoned.
TIMEOUT = 20
# An error was returned directly when making a request buildbucket.
BUILDBUCKET_REQUEST_ERROR = 30
# Buildbucket ran the try job and reported an error.
CI_REPORTED_ERROR = 40
# An infra failure occurred according to the recipe report.
INFRA_FAILURE = 50
