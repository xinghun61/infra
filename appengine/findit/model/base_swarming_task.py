# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model import analysis_status

class BaseSwarmingTask(ndb.Model):
  """Represents the progress of a general swarming task."""
  # The id of the Swarming task scheduled or running on Swarming Server.
  task_id = ndb.StringProperty(indexed=True)

  # A dict to keep track of running information for each test:
  # number of total runs, number of each status (such as 'SUCCESS' or 'FAILED')
  tests_statuses = ndb.JsonProperty(indexed=False, compressed=True)

  # The status of the swarming task.
  status = ndb.IntegerProperty(
      default=analysis_status.PENDING, indexed=False)

  # The revision of the failed build.
  build_revision = ndb.StringProperty(indexed=False)

  # Time when the task is created.
  created_time = ndb.DateTimeProperty(indexed=True)
  # Time when the task is started.
  started_time = ndb.DateTimeProperty(indexed=False)
  # Time when the task is completed.
  completed_time = ndb.DateTimeProperty(indexed=False)

  # parameters need to be stored and analyzed later.
  parameters = ndb.JsonProperty(default={}, indexed=False, compressed=True)
