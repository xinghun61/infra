# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import analysis_status


class BuildAheadTryJob(ndb.Model):
  """Represents a single build ahead tryjob.

  Note that this doesn't extend BaseTryJob because this doesn't have multiple
  tryjob ids per entity, instead, the try job's buildbucket id is the key for
  the object.
  """

  # Whether the build is running, index required to get which builds to monitor.
  running = ndb.BooleanProperty(default=True, indexed=True)

  # The build as returned by buildbucket.
  last_buildbucket_response = ndb.JsonProperty(indexed=False, compressed=True)

  # win|unix|mac|android|ios
  platform = ndb.StringProperty(indexed=True)

  cache_name = ndb.StringProperty()

  @staticmethod
  def Get(build_id):
    return ndb.Key(BuildAheadTryJob, str(build_id)).get()

  @staticmethod
  def Create(build_id, platform, cache_name):
    try_job = BuildAheadTryJob(
        key=ndb.Key(BuildAheadTryJob, str(build_id)),
        platform=platform,
        cache_name=cache_name)
    return try_job

  @staticmethod
  def RunningJobs(platform=None):
    query = BuildAheadTryJob.query(BuildAheadTryJob.running == True)
    if platform:
      query = query.filter(BuildAheadTryJob.platform == platform)
    return query.fetch()

  def MarkComplete(self, metadata):
    self.running = False
    self.last_buildbucket_response = metadata
    self.put()

  @property
  def BuildId(self):
    return self.key.pairs()[0][1]
