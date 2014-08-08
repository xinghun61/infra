# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class Master(ndb.Model):
  name = ndb.StringProperty()
  generated = ndb.DateTimeProperty(auto_now_add=True)


class Builder(ndb.Model):
  name = ndb.StringProperty()
  generated = ndb.DateTimeProperty(auto_now_add=True)
  steps = ndb.PickleProperty()


class Step(ndb.Model):
  name = ndb.StringProperty()
  generated = ndb.DateTimeProperty(auto_now_add=True)
  builders = ndb.PickleProperty()


class BuildStepRecord(ndb.Model):
  master = ndb.StringProperty()
  builder = ndb.StringProperty()
  buildnumber = ndb.IntegerProperty()
  revision = ndb.StringProperty()
  stepname = ndb.StringProperty()
  step_start = ndb.DateTimeProperty()
  step_time = ndb.FloatProperty()
  result = ndb.IntegerProperty()
  generated = ndb.DateTimeProperty(auto_now_add=True)


class BuildStepStatistic(ndb.Model):
  count = ndb.IntegerProperty()
  median = ndb.FloatProperty()
  seventyfive = ndb.FloatProperty()
  ninety = ndb.FloatProperty()
  ninetynine = ndb.FloatProperty()
  maximum = ndb.FloatProperty()
  mean = ndb.FloatProperty()
  stddev = ndb.FloatProperty()
  failure_count = ndb.FloatProperty()
  failure_rate = ndb.FloatProperty()
  

class BuildStatisticRecord(ndb.Model):
  start_time = ndb.DateTimeProperty()
  end_time_exclusive = ndb.DateTimeProperty()
  record = ndb.StringProperty()
  stats = ndb.StructuredProperty(BuildStepStatistic)
  generated = ndb.DateTimeProperty(auto_now_add=True)
