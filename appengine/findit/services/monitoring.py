# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for monitoring operations.

It provides functions to:
  * Monitor when try job is triggered.
"""

from common import monitoring


def OnTryJobTriggered(try_job_type, master_name, builder_name):
  """Records when a try job is triggered."""
  monitoring.try_jobs.increment({
      'operation': 'trigger',
      'type': try_job_type,
      'master_name': master_name,
      'builder_name': builder_name,
  })
