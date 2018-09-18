# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.isolated_tests import IsolatedTests
from dto.try_job_report import TryJobReport


class FlakeTryJobReport(TryJobReport):
  """Represents output of a flake try job."""
  # Maps the step to the isolate sha of the compiled binaries.
  isolated_tests = IsolatedTests
