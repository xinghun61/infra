# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis import WfAnalysis
from model import wf_analysis_result_status


_DEFAULT_DISPLAY_COUNT = 500


class ListAnalyses(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE
  
  def HandleGet(self):
    """Shows a list of Findit analysis results in HTML page."""
    if self.request.get('count'):
      count = int(self.request.get('count'))
    else:
      count = _DEFAULT_DISPLAY_COUNT

    if self.request.get('triage') == '1':
      analysis_query = WfAnalysis.query(ndb.AND(
          WfAnalysis.result_status>wf_analysis_result_status.FOUND_CORRECT, 
          WfAnalysis.result_status<wf_analysis_result_status.NOT_FOUND_CORRECT))
    else:
      analysis_query = WfAnalysis.query(ndb.AND(
          WfAnalysis.result_status>=wf_analysis_result_status.FOUND_CORRECT, 
          WfAnalysis.result_status<wf_analysis_result_status.FOUND_UNTRIAGED))

    analysis_results = analysis_query.order(
        WfAnalysis.result_status, -WfAnalysis.build_start_time).fetch(count)
    analyses = []

    def FormatDatetime(datetime):
      if not datetime:
        return None
      else:
        return datetime.strftime('%Y-%m-%d %H:%M:%S UTC')

    for analysis_result in analysis_results:
      analysis = {
          'master_name': analysis_result.master_name,
          'builder_name': analysis_result.builder_name,
          'build_number': analysis_result.build_number,
          'build_start_time': FormatDatetime(analysis_result.build_start_time),
          'status': analysis_result.status,
          'status_description': analysis_result.status_description,
          'suspected_cls': analysis_result.suspected_cls,
          'result_status': analysis_result.result_status_description
      }
      analyses.append(analysis)

    data = {
        'analyses': analyses
    }
    return {'template': 'list_analyses.html', 'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
