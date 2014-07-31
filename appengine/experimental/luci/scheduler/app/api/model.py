# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from app.framework import success, failure, abort, DefaultRootModel


DEFAULT_SCHEDULER = ndb.Key('Scheduler', 'default')


class JobState(object): # enum
  QUEUED = 'queued'
  STARTED = 'started'
  COMPLETED = 'completed'
  FAILED = 'failed'

class Job(DefaultRootModel):
  _default_root = DEFAULT_SCHEDULER

  name = ndb.StringProperty(required=True)
  state = ndb.StringProperty(default=JobState.QUEUED)
  time_queued = ndb.DateTimeProperty(required=True, auto_now_add=True)

  binary = ndb.StringProperty(required=True)
  params = ndb.StringProperty(repeated=True)

  reverse_deps = ndb.StringProperty(repeated=True)
  num_deps = ndb.IntegerProperty(required=True, default=0)

  result_hash = ndb.StringProperty()
  log_path = ndb.StringProperty()

  worker = ndb.StringProperty()

class Worker(DefaultRootModel):
  _default_root = DEFAULT_SCHEDULER

  last_seen = ndb.DateTimeProperty(required=True, auto_now=True)
  job = ndb.StringProperty()
