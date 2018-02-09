# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for operating on tests run in swarming."""

import logging

from common.findit_http_client import FinditHttpClient
from dto.test_location import TestLocation
from waterfall import swarming_util

_FINDIT_HTTP_CLIENT = FinditHttpClient()


def GetTestLocation(task_id, test_name):
  """Gets the filepath and line number of a test from swarming.

  Args:
    task_id (str): The swarming task id to query.
    test_name (str): The name of the test whose location to return.

  Returns:
    (TestLocation): The file path and line number of the test, or None
        if the test location was not be retrieved.

  """
  task_output = swarming_util.GetIsolatedOutputForTask(task_id,
                                                       _FINDIT_HTTP_CLIENT)

  if not task_output:
    logging.error('No isolated output returned for %s', task_id)
    return None

  test_locations = task_output.get('test_locations')

  if not test_locations:
    logging.error('test_locations not found for task %s', task_id)
    return None

  test_location = test_locations.get(test_name)

  if not test_location:
    logging.error('test_location not found for %s', test_name)
    return None

  return TestLocation.FromSerializable(test_location)
