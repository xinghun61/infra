# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.flake_try_job_report import FlakeTryJobReport
from libs.structured_object import StructuredObject


class FlakeTryJobResult(StructuredObject):
  """Reoresents a flake try job result stored in a FlakeTryJob."""
  # The url to the try job build page.
  # TODO(crbug.com/796646): Convert url to
  # master/builder/build_number/buildbucket_build_id record.
  url = basestring

  # The try job ID of the try job itself.
  try_job_id = basestring

  # The resulting output of the try job.
  report = FlakeTryJobReport
