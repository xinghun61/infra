# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.base_handler import BaseHandler
from common.base_handler import Permission
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
          'test_name': master_flake_analysis.test_name
      })

    return {
        'template': 'flake/dashboard.html',
        'data': data
    }
