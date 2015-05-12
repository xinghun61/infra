# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime

from google.appengine.ext import ndb

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis import WfAnalysis
from model import wf_analysis_result_status


_DEFAULT_DISPLAY_COUNT = 500


class ListAnalyses(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE
  
  def HandleGet(self):
    """Shows a list of Findit analysis results in HTML page.

    By default the page will display all the results under status FOUND_CORRECT,
    FOUND_INCORRECT and NOT_FOUND_INCORRECT.

    Avaliable parameters:
      count: Parameter for number of analysis result to be displayed.
      result_status: Parameter to specify the result_status of the results.
      triage: Parameter for internal use. The page will display analysis results
        under status FOUND_INCORRECT, NOT_FOUND_INCORRECT, FOUND_UNTRIAGED and
        NOT_FOUND_UNTRIAGED.
      days: Parameter to decide only display results within a fixed amount of 
        days. This parameter will turn off triage parameter and display all the
        results regardless of result_status.
    """
    # TODO: Add a dropdown for users to select single result_status.
    status_code = int(self.request.get('result_status','-1'))
    if status_code >= 0:
      analysis_query = WfAnalysis.query(WfAnalysis.result_status==status_code)
    elif self.request.get('triage') == '1':
      analysis_query = WfAnalysis.query(ndb.AND(
          WfAnalysis.result_status>wf_analysis_result_status.FOUND_CORRECT, 
          WfAnalysis.result_status<wf_analysis_result_status.NOT_FOUND_CORRECT))
    else:
      analysis_query = WfAnalysis.query(ndb.AND(
          WfAnalysis.result_status>=wf_analysis_result_status.FOUND_CORRECT, 
          WfAnalysis.result_status<wf_analysis_result_status.FOUND_UNTRIAGED))

    if self.request.get('count'):
      count = int(self.request.get('count'))
    else:
      count = _DEFAULT_DISPLAY_COUNT

    if self.request.get('days'):  # pragma: no cover
      start_date = datetime.datetime.utcnow() - datetime.timedelta(
          int(self.request.get('days')))
      start_date = start_date.replace(
          hour=0, minute=0, second=0, microsecond=0)

      if status_code >= 0:
        analysis_results = analysis_query.filter(
            WfAnalysis.build_start_time>=start_date).order(
            -WfAnalysis.build_start_time).fetch(count)
      else:
        analysis_results = WfAnalysis.query(
            WfAnalysis.build_start_time>=start_date).order(
            -WfAnalysis.build_start_time).fetch(count)
    else:
      analysis_results = analysis_query.order(
          WfAnalysis.result_status, -WfAnalysis.build_start_time).fetch(count)

    analyses = []

    def FormatDatetime(start_time):
      if not start_time:
        return None
      else:
        return start_time.strftime('%Y-%m-%d %H:%M:%S UTC')

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
        'analyses': analyses,
        'triage': self.request.get('triage', '-1'),
        'days': self.request.get('days', '-1'),
        'count': self.request.get('count', '-1'),
        'result_status': self.request.get('result_status', '-1')
    }
    return {'template': 'list_analyses.html', 'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
