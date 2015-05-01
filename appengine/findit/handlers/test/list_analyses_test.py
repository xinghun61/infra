# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

import webapp2

from testing_utils import testing

from handlers import list_analyses
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model import wf_analysis_result_status
from waterfall import identify_culprit_pipeline


class ListAnalysesTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [('/list-analyses', list_analyses.ListAnalyses),], debug=True)

  def testListAnalysesHandler(self):
    response = self.test_app.get('/list-analyses')
    self.assertEqual(200, response.status_int)

  def _AddAnalysisResult(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.ANALYZING
    analysis.put()
    return analysis

  def _AddAnalysisResults(self):
    analyses = []

    for i in range(0, 10):
      analyses.append(self._AddAnalysisResult('m', 'b', i))

    self._AddAnalysisResult('chromium.linux', 'Linux GN', 26120)
    analyses.append(WfAnalysis.Get('chromium.linux', 'Linux GN', 26120))

    analyses[1].status = wf_analysis_status.ANALYZED
    analyses[2].status = wf_analysis_status.ANALYZED
    analyses[3].status = wf_analysis_status.ANALYZED
    analyses[4].status = wf_analysis_status.ERROR
    analyses[7].status = wf_analysis_status.ANALYZED
    analyses[9].status = wf_analysis_status.ANALYZED
    analyses[10].status = wf_analysis_status.ANALYZED

    analyses[2].build_start_time = datetime.datetime(2015, 1, 1, 
                                                     9, 27, 40, 453434)
    analyses[7].build_start_time = datetime.datetime(2015, 1, 2, 
                                                     11, 05, 50, 123456)
    analyses[10].build_start_time = datetime.datetime(2015, 1, 2, 
                                                      13, 23, 57, 563434)

    analyses[1].result = {
       'failures': [
           {
               'step_name': 'b',
               'first_failure': 1,
               'last_pass': None,
               'suspected_cls': [
                   {
                       'build_number': 1,
                       'repo_name': 'chromium',
                       'revision': 'r99_1',
                       'commit_position': None,
                       'url': None,
                       'score': 5,
                       'hints': {
                           'added x/y/f99_1.cc (and it was in log)': 5,
                       },
                   }
               ],
           }
       ]
    }

    analyses[2].result = {
       'failures': [
           {
               'step_name': 'a',
               'first_failure': 2,
               'last_pass': None,
               'suspected_cls': [],
           },
           {
               'step_name': 'b',
               'first_failure': 1,
               'last_pass': None,
               'suspected_cls': [],
           }
       ]
    }

    analyses[3].result = {
       'failures': [
           {
               'step_name': 'a',
               'first_failure': 3,
               'last_pass': None,
               'suspected_cls': [],
           },
           {
               'step_name': 'b',
               'first_failure': 2,
               'last_pass': None,
               'suspected_cls': [],
           }
       ]
    }

    analyses[7].result = {
       'failures': [
           {
               'step_name': 'a',
               'first_failure': 7,
               'last_pass': None,
               'suspected_cls': [
                   {
                       'build_number': 7,
                       'repo_name': 'chromium',
                       'revision': 'r99_2',
                       'commit_position': None,
                       'url': None,
                       'score': 1,
                       'hints': {
                           'modified f99_2.cc (and it was in log)': 1,
                       },
                   },
                   {
                       'build_number': 7,
                       'repo_name': 'chromium',
                       'revision': 'r99_6',
                       'commit_position': None,
                       'url': None,
                       'score': 5,
                       'hints': {
                           'added x/y/f99_7.cc (and it was in log)': 5,
                       },
                   }
               ],
           },
           {
               'step_name': 'b',
               'first_failure': 7,
               'last_pass': None,
               'suspected_cls': [
                   {
                       'build_number': 7,
                       'repo_name': 'chromium',
                       'revision': 'r99_1',
                       'commit_position': None,
                       'url': 'https://chromium.googlesource.com/chromium/'
                              'src/r99_1',
                       'score': 5,
                       'hints': {
                           'added x/y/f99_1.cc (and it was in log)': 5,
                       },
                   }
               ],
           }
       ]
    }

    analyses[9].result = {
       'failures': [
           {
               'step_name': 'a',
               'first_failure': 9,
               'last_pass': None,
               'suspected_cls': [],
           },
           {
               'step_name': 'b',
               'first_failure': 9,
               'last_pass': None,
               'suspected_cls': [
                   {
                       'build_number': 9,
                       'repo_name': 'chromium',
                       'revision': 'r99_9',
                       'commit_position': None,
                       'url': None,
                       'score': 1,
                       'hints': {
                           'modified f99_9.cc (and it was in log)': 1,
                       },
                   }
               ],
           }
       ]
    }

    analyses[10].result = {
       'failures': [
           {
               'step_name': 'a',
               'first_failure': 10,
               'last_pass': None,
               'suspected_cls': [
                   {
                       'build_number': 10,
                       'repo_name': 'chromium',
                       'revision': 'r99_10',
                       'commit_position': None,
                       'url': None,
                       'score': 5,
                       'hints': {
                           'added x/f99_10.cc (and it was in log)': 5,
                       },
                   }
               ],
           },
           {
               'step_name': 'b',
               'first_failure': 10,
               'last_pass': None,
               'suspected_cls': [                   {
                       'build_number': 10,
                       'repo_name': 'chromium',
                       'revision': 'r99_10',
                       'commit_position': None,
                       'url': None,
                       'score': 1,
                       'hints': {
                           'modified x/f99_9.cc (and it was in log)': 1,
                       },
                   }
               ],
           }
       ]
    }

    for analysis in analyses:
      analysis.suspected_cls = identify_culprit_pipeline._GetSuspectedCLs(
          analysis.result)
      analysis.result_status = (identify_culprit_pipeline.
          _GetResultAnalysisStatus(analysis.result))
      analysis.put()

    analyses[1].result_status = wf_analysis_result_status.FOUND_INCORRECT
    analyses[1].put()
    analyses[3].result_status = wf_analysis_result_status.NOT_FOUND_INCORRECT
    analyses[3].put()
    analyses[10].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[10].put()

    return analyses

  def testDisplayAggregatedBuildAnalysisResults(self):
    self._AddAnalysisResults()

    expected_result = {  
        'analyses': [
            {
                'master_name': 'chromium.linux',
                'builder_name': 'Linux GN',
                'build_number': 26120,
                'build_start_time': '2015-01-02 13:23:57 UTC',
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls': [
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_10',
                        'commit_position': None,
                        'url': None
                    }
                ],
                'result_status': 'Correct - Found'
            },
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 1,
                'build_start_time': None,
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls':[
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_1',
                        'commit_position': None,
                        'url': None
                    }
                ],
                'result_status': 'Incorrect - Found'
            },
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 3,
                'build_start_time': None,
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls':[],
                'result_status': 'Incorrect - Not Found'
            }
        ]
    }

    response_json = self.test_app.get('/list-analyses?format=json&count=5')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testDisplayAggregatedBuildAnalysisResultsTriage(self):
    self._AddAnalysisResults()

    expected_result = {  
        'analyses': [
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 1,
                'build_start_time': None,
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls':[
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_1',
                        'commit_position': None,
                        'url': None
                    }
                ],
                'result_status': 'Incorrect - Found'
            },
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 3,
                'build_start_time': None,
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls':[],
                'result_status': 'Incorrect - Not Found'
            },
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 7,
                'build_start_time': '2015-01-02 11:05:50 UTC',
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls': [
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_2',
                        'commit_position': None,
                        'url': None
                    },
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_6',
                        'commit_position': None,
                        'url': None
                    },
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_1',
                        'commit_position': None,
                        'url': 'https://chromium.googlesource.com'
                               '/chromium/src/r99_1'
                    }
                ],
                'result_status': 'Untriaged - Found'
            },
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 9,
                'build_start_time': None,
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls': [
                    {
                        'repo_name': 'chromium',
                        'revision': 'r99_9',
                        'commit_position': None,
                        'url': None
                    }
                ],
                'result_status': 'Untriaged - Found'
            },
            {
                'master_name': 'm',
                'builder_name': 'b',
                'build_number': 2,
                'build_start_time': '2015-01-01 09:27:40 UTC',
                'status': 70,
                'status_description': 'Analyzed',
                'suspected_cls': [],
                'result_status': 'Untriaged - Not Found'
            }
        ]
    }

    response_json = self.test_app.get('/list-analyses?format=json&triage=1')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)
