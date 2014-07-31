# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

SLO_BUILDTIME_MEDIAN = 30 * 60  # 30 minutes
SLO_BUILDTIME_MAX = 60 * 60  # 60 minutes


class Project(ndb.Model):
  pass


class CqStat(ndb.Model):
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  length = ndb.IntegerProperty(required=True)
  min = ndb.FloatProperty(default=0)
  max = ndb.FloatProperty(default=0)
  mean = ndb.FloatProperty(default=0)
  p10 = ndb.FloatProperty(default=0)
  p25 = ndb.FloatProperty(default=0)
  p50 = ndb.FloatProperty(default=0)
  p75 = ndb.FloatProperty(default=0)
  p90 = ndb.FloatProperty(default=0)
  p95 = ndb.FloatProperty(default=0)
  p99 = ndb.FloatProperty(default=0)


class Tree(ndb.Model):
  pass


class BuildSLOOffender(ndb.Model):
  tree = ndb.StringProperty()
  master = ndb.StringProperty()
  builder = ndb.StringProperty()
  buildnumber = ndb.IntegerProperty()
  buildtime = ndb.FloatProperty()
  result = ndb.IntegerProperty()
  revision = ndb.IntegerProperty()
  # Store these with each build, in case we change the SLO, so that we know
  # what SLO was not met.
  slo_median_buildtime = ndb.FloatProperty(default=SLO_BUILDTIME_MEDIAN)
  slo_max_buildtime = ndb.FloatProperty(default=SLO_BUILDTIME_MAX)


class BuildTimeStat(ndb.Model):
  timestamp = ndb.DateTimeProperty()
  slo_offenders = ndb.StructuredProperty(BuildSLOOffender, repeated=True)
  num_builds = ndb.IntegerProperty()
  num_over_median_slo = ndb.IntegerProperty()
  num_over_max_slo = ndb.IntegerProperty()
