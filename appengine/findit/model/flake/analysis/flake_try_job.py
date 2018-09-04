# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

from google.appengine.ext import ndb

from model.base_try_job import BaseTryJob


class FlakeTryJob(BaseTryJob):
  """Represents a try job results for a check flake try job."""
  # A list of dict containing results and urls of each flake try job.
  # For example:
  # [
  #      {
  #           'report': (dict) The 'result' dict of the try job,
  #           'url': (str) The url to the try job,
  #           'try_job_id': (str) The try job id.
  #      },
  #      ...
  # ]
  flake_results = ndb.JsonProperty(indexed=False, compressed=True)

  @classmethod
  def GetStepName(cls, key):
    return key.pairs()[0][1].split('/')[2]

  @classmethod
  def GetTestName(cls, key):
    return base64.b64decode(key.pairs()[0][1].split('/')[3])

  @classmethod
  def GetGitHash(cls, key):
    return key.pairs()[0][1].split('/')[4]

  @ndb.ComputedProperty
  def step_name(self):
    return self.GetStepName(self.key)

  @ndb.ComputedProperty
  def test_name(self):
    return self.GetTestName(self.key)

  @ndb.ComputedProperty
  def git_hash(self):
    return self.GetGitHash(self.key)

  @staticmethod
  def _CreateTryJobId(master_name, builder_name, step_name, test_name,
                      git_hash):  # pragma: no cover
    """Creates an ID to associate with this try job.

    Args:
      master_name (str): The name of the master the flake was detected on.
      builder_name (str): the name of the builder the flake was detected on.
      step_name (str): The name of the step the flake was detected on.
      test_name (str): The original name of the test that flaked. This will be
        converted to base64 to avoid special characters in the test name
        causing issues.
      git_hash (str): The revision the try job will sync to and run against.

    Returns:
      The string ID to be associated with this try job.
    """
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return '%s/%s/%s/%s/%s' % (master_name, builder_name, step_name,
                               encoded_test_name, git_hash)

  @staticmethod
  def _CreateKey(master_name, builder_name, step_name, test_name,
                 git_hash):  # pragma: no cover
    return ndb.Key('FlakeTryJob',
                   FlakeTryJob._CreateTryJobId(master_name, builder_name,
                                               step_name, test_name, git_hash))

  @staticmethod
  def Create(master_name, builder_name, step_name, test_name, git_hash):
    flake_try_job = FlakeTryJob(key=FlakeTryJob._CreateKey(
        master_name, builder_name, step_name, test_name, git_hash))
    flake_try_job.flake_results = flake_try_job.flake_results or []
    flake_try_job.try_job_ids = flake_try_job.try_job_ids or []
    return flake_try_job

  @staticmethod
  def Get(master_name, builder_name, step_name, test_name, git_hash):
    return FlakeTryJob._CreateKey(master_name, builder_name, step_name,
                                  test_name, git_hash).get()
