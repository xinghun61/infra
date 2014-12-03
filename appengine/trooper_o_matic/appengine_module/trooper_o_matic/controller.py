# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from appengine_module.trooper_o_matic import models


def get_cq_stats(project):
  project_key = ndb.Key(models.Project, project)
  single_run_data = models.CqStat.query(ancestor=project_key).order(
      -models.CqStat.timestamp).fetch(limit=100)
  single_run_data = [run for run in single_run_data if run.p50]
  single_run_data.reverse()
  queue_time_data = models.CqTimeInQueueForPatchStat.query(
      ancestor=project_key).order(-models.CqStat.timestamp).fetch(limit=100)
  queue_time_data = [run for run in queue_time_data if run.p50]
  queue_time_data.reverse()
  total_time_data = models.CqTotalTimeForPatchStat.query(
      ancestor=project_key).order(-models.CqStat.timestamp).fetch(limit=100)
  total_time_data = [run for run in total_time_data if run.p50]
  total_time_data.reverse()

  return {
      'single_run_data': single_run_data,
      'queue_time_data': queue_time_data,
      'total_time_data': total_time_data,
  }
