# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.isolated_tests import IsolatedTests
from libs.structured_object import StructuredObject


class FlakeTryJobReport(StructuredObject):
  """Represents output of a flake try job."""
  # Maps the step to the isolate sha of the compiled binaries.
  isolated_tests = IsolatedTests

  # Info about the try job itself.
  # TODO(crbug.com/796428): Convert metadata to a StructuredObject.
  metadata = dict

  # The recipe keeps track of the revisions that were checked out on the bot's
  # work directory and local git cache with the purpose of selecting a bot that
  # has the revision we want to test if possible such that we reduce the amount
  # of data that needs to be downloaded before the recipe starts performing
  # useful work.
  previously_cached_revision = basestring
  previously_checked_out_revision = basestring

  # Legacy field returned in try job results.
  # TODO(crbug.com/786518): Remove after switching to merged pipeline.
  result = dict
