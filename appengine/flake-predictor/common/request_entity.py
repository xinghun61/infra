# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import threading

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

from protorpc import messages


class Status(messages.Enum):
  PENDING = 0
  RUNNING = 1
  COMPLETED = 2
  FAILED = 3

class Request(ndb.Model):
  """ndb model for findit API requests

  ndb model for storing information about findit swarming rerun requests and
  what the status of those requests are.
  """
  master_name = ndb.StringProperty()
  builder_name = ndb.StringProperty()
  build_number = ndb.IntegerProperty()
  step_name = ndb.StringProperty()
  test_name = ndb.StringProperty()
  test_results = ndb.IntegerProperty(repeated=True, indexed=False)
  swarming_response = ndb.JsonProperty(default=None)
  status = msgprop.EnumProperty(Status, default=Status.PENDING)

class RequestManager(ndb.Model):
  """ndb model for managing findit API requests

  ndb model for storing keys to requests and the number of requests made. It
  stores the keys to requests based on their status.
  """
  pending = ndb.KeyProperty(repeated=True)
  running = ndb.KeyProperty(repeated=True)
  completed = ndb.KeyProperty(repeated=True)
  num_scheduled = ndb.IntegerProperty(default=0)
  # Disabling in-context cache for consistency because this code will be called
  # from different threads and each thread has its own context/cache
  # https://cloud.google.com/appengine/docs/standard/python/ndb/cache#incontext
  _use_cache = False

  @staticmethod
  def load():
    manager = ndb.Key('RequestManager', 'singleton').get()
    return manager or RequestManager(id='singleton')

  def add_request(self, request):
    """ Generate request key and store it. Failed requests are discarded """
    if request.status is Status.PENDING:
      self.pending.append(request.put())
    elif request.status is Status.RUNNING:
      self.running.append(request.put())
    elif request.status is Status.COMPLETED:
      self.completed.append(request.put())

  def save(self):
    assert self.key.id() == 'singleton'
    return self.put()

  @staticmethod
  def delete():
    """ Deletes all of the entities managed """
    manager = RequestManager.load()
    ndb.delete_multi(manager.pending)
    ndb.delete_multi(manager.running)
    ndb.delete_multi(manager.completed)
    manager.key.delete()
