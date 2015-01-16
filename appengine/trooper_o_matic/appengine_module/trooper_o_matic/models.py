# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from endpoints_proto_datastore.ndb import EndpointsModel


SLO_BUILDTIME_MEDIAN = float(90 * 60)   # 90 minutes
SLO_BUILDTIME_MAX = float(8 * 60 * 60)  # 480 minutes, lower when
                                        # crbug.com/434965 is fixed.

SLO_BUILDTIME_PER_BOT_MEDIAN = {}
SLO_BUILDTIME_PER_BOT_MAX = {}

# False rejection percentage limits, from 0.0 to 100.0.
SLO_WEEKLY_FALSE_REJECTION_MAX = 15.0
SLO_HOURLY_FALSE_REJECTION_MAX = 15.0

BUILDTIME_PER_BOT_MAX = {}


class Project(ndb.Model):
  pass


class CqStat(EndpointsModel):
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  length = ndb.IntegerProperty(required=True)
  # TODO(alancutter): Remove these fields now that we query them from
  # chromium-cq-status.
  min = ndb.FloatProperty()
  max = ndb.FloatProperty()
  mean = ndb.FloatProperty()
  p10 = ndb.FloatProperty()
  p25 = ndb.FloatProperty()
  p50 = ndb.FloatProperty()
  p75 = ndb.FloatProperty()
  p90 = ndb.FloatProperty()
  p95 = ndb.FloatProperty()
  p99 = ndb.FloatProperty()


class CqTimeInQueueForPatchStat(CqStat):
  pass


class CqTotalTimeForPatchStat(CqStat):
  pass


class TreeOpenStat(ndb.Model):
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  num_days = ndb.IntegerProperty(required=True)
  percent_open = ndb.FloatProperty(required=True)


class Tree(ndb.Model):
  pass


class BuildSLOOffender(EndpointsModel):
  tree = ndb.StringProperty()
  master = ndb.StringProperty()
  builder = ndb.StringProperty()
  buildnumber = ndb.IntegerProperty()
  buildtime = ndb.FloatProperty()
  result = ndb.IntegerProperty()
  revision = ndb.StringProperty()
  # Store these with each build, in case we change the SLO, so that we know
  # what SLO was not met.
  slo_median_buildtime = ndb.FloatProperty(default=SLO_BUILDTIME_MEDIAN)
  slo_max_buildtime = ndb.FloatProperty(default=SLO_BUILDTIME_MAX)
  generated = ndb.DateTimeProperty(auto_now_add=True)


class BuildTimeStat(ndb.Model):
  timestamp = ndb.DateTimeProperty()
  slo_offenders = ndb.StructuredProperty(BuildSLOOffender, repeated=True)
  num_builds = ndb.IntegerProperty()
  num_over_median_slo = ndb.IntegerProperty()
  num_over_max_slo = ndb.IntegerProperty()


class FalseRejectionSLOOffender(EndpointsModel):
  hourly_patchset_attempts = ndb.IntegerProperty()
  hourly_patchset_rejections = ndb.IntegerProperty()
  weekly_patchset_attempts = ndb.IntegerProperty()
  weekly_patchset_rejections = ndb.IntegerProperty()
  weekly = ndb.FloatProperty()  # From 0.0 to 100.0.
  hourly = ndb.FloatProperty()  # From 0.0 to 100.0.
  slo_weekly_max = ndb.FloatProperty(default=SLO_WEEKLY_FALSE_REJECTION_MAX)
  slo_hourly_max = ndb.FloatProperty(default=SLO_HOURLY_FALSE_REJECTION_MAX)
  generated = ndb.DateTimeProperty(auto_now_add=True)
