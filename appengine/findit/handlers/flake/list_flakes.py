# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.base_handler import BaseHandler
from common.base_handler import Permission
from common import time_util
from model.flake.master_flake_analysis import MasterFlakeAnalysis


def FilterMasterFlakeAnalysis(master_flake_analysis_query, master_name,
                              builder_name, build_number, step_name, test_name):
  if master_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.master_name == master_name)
  if builder_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.builder_name == builder_name)
  if build_number:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.build_number == build_number)
  if step_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.step_name == step_name)
  if test_name:
    master_flake_analysis_query = master_flake_analysis_query.filter(
        MasterFlakeAnalysis.test_name == test_name)
  if not (master_name or builder_name or build_number or
          step_name or test_name):
    master_flake_analysis_query.order(-MasterFlakeAnalysis.request_time)
  return master_flake_analysis_query.fetch()


class ListFlakes(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    master_name = self.request.get('master_name').strip()
    builder_name = self.request.get('builder_name').strip()
    build_number = self.request.get('build_number').strip()
    if build_number:
      build_number = int(build_number)
    step_name = self.request.get('step_name').strip()
    test_name = self.request.get('test_name').strip()

    master_flake_analyses = FilterMasterFlakeAnalysis(
        MasterFlakeAnalysis.query(), master_name, builder_name, build_number,
        step_name, test_name)
    data = {'master_flake_analyses': []}

    for master_flake_analysis in master_flake_analyses:
      data['master_flake_analyses'].append({
          'master_name': master_flake_analysis.master_name,
          'builder_name': master_flake_analysis.builder_name,
          'build_number': master_flake_analysis.build_number,
          'step_name': master_flake_analysis.step_name,
          'test_name': master_flake_analysis.test_name,
          'status': master_flake_analysis.status_description,
          'suspected_build': master_flake_analysis.suspected_flake_build_number,
          'request_time': time_util.FormatDatetime(
              master_flake_analysis.request_time),
      })

    # TODO (stgao): use index instead of in-memory sort.
    # Index doesn't work for now, possibly due to legacy data.
    data['master_flake_analyses'].sort(
        key=lambda e : e['request_time'], reverse=True)

    return {
        'template': 'flake/dashboard.html',
        'data': data
    }
