# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Structured object representing the flakiness at a commit position."""
from dto.swarming_task_error import SwarmingTaskError
from libs.list_of_basestring import ListOfBasestring
from libs.structured_object import StructuredObject


class Flakiness(StructuredObject):
  """Represents the flakiness with other metadata at a commit position."""
  # The url to the build page of the build whose artifacts were used to generate
  # this structure, if any.

  # Used for fallback logic to searching buildbot only.
  # TODO(crbug.com/872992): Remove build_number once LUCI migration is complete.
  build_number = int

  # TODO (crbug.com/876557): Consolidate build_url and try_job_url using
  # build_id once all builds are on LUCI.
  build_url = basestring

  # The commit position at which flakiness is being evaluated.
  commit_position = int

  # The last-encountered error from Swarming.
  error = SwarmingTaskError

  # The number of times a swarming task had an error while generating this
  # structure.
  failed_swarming_task_attempts = int

  # The cumulative number of iterations that were run.
  iterations = int

  # The measured pass rate of the test when run against commit_position.
  pass_rate = float

  # The git hash being evaluated.
  revision = basestring

  # The total number of seconds to run all iterations thus far.
  total_test_run_seconds = int

  # The URL to the try job that generated the results this structure represents,
  # if any.
  try_job_url = basestring

  # The list of swarming tasks IDs responsible for generating this structure.
  task_ids = ListOfBasestring
