# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from google.appengine.ext import ndb

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis import WfAnalysis
from model import wf_analysis_result_status


def _GetFailedStepsForEachCL(analysis):
  """Gets suspected CLs and their corresponding failed steps."""
  suspected_cl_steps = {}
  if (analysis is None or analysis.result is None or
      not analysis.result['failures']):
    return suspected_cl_steps

  for failure in analysis.result['failures']:
    for suspected_cl in failure['suspected_cls']:
      cl_key = suspected_cl['repo_name'] + ',' + suspected_cl['revision']
      if not suspected_cl_steps.get(cl_key):
        suspected_cl_steps[cl_key] = [failure['step_name']]
      else:
        suspected_cl_steps[cl_key].append(failure['step_name'])
  return suspected_cl_steps


def _AnalysesForDuplicateFailures(analysis, another_analysis):
  """Checks if two analyses are from analyzing two duplicate build failures.

  The two results are duplicates if:
  1. They have the same failed steps
  2. They have found the same suspected CLs
  In theory we should also check if these two analyses have the same master_name
  and builder_name, but it's unnecessary here since they are consecutive.
  """
  if sorted(analysis.suspected_cls) != sorted(another_analysis.suspected_cls):
    return False

  if (_GetFailedStepsForEachCL(analysis) !=
      _GetFailedStepsForEachCL(another_analysis)):
    return False

  return True


def _ModifyStatusIfDuplicate(analysis):
  """Sets duplicate status to analyses of duplicating build failures.

  For the result with result_status FOUND_UNTRIAGED, if it meets
  below conditions:
    1. the build failure is in a series of continuous failures with same step
        failure
    2. all the faliures share the same suspected CL(s)
    3. the first and the last result of these failures have been triaged
    4. the first and the last result are both correct or incorrect
  Mark the result as 'FOUND_CORRECT_DUPLICATE' or 'FOUND_INCORRECT_DUPLICATE'.
  """
  if analysis.result_status != wf_analysis_result_status.FOUND_UNTRIAGED:
    # It may have been taken care of when we check duplicates for previous
    # result in the serie.
    return

  master_name = analysis.master_name
  builder_name = analysis.builder_name
  build_number = analysis.build_number

  first_build_analysis = WfAnalysis.Get(master_name,
                                        builder_name, build_number-1)

  if not first_build_analysis:
    # Current build is not within a serie of continuous build failures.
    return

  if first_build_analysis.result_status not in (
      wf_analysis_result_status.FOUND_CORRECT,
      wf_analysis_result_status.FOUND_INCORRECT):
    # Findit doesn't find suspected CLs for previous build or
    # it has not been triaged.
    return

  # Stores the build failure analyses in a row, except the first and last one,
  # and set their result_statuses to 'FOUND_CORRECT_DUPLICATE' or
  # 'FOUND_INCORRECT_DUPLICATE' if they really are duplicates.
  build_analyses = []

  build_number_cursor = build_number
  build_analysis_cursor = analysis

  while True:
    if not build_analysis_cursor:  # The last failed build is not triaged.
      return

    elif build_analysis_cursor.result_status in (
        wf_analysis_result_status.FOUND_CORRECT,
        wf_analysis_result_status.FOUND_INCORRECT):
      # The last failed build is reached and it has been triaged.
      if (first_build_analysis.result_status !=
          build_analysis_cursor.result_status or
          not _AnalysesForDuplicateFailures(
              first_build_analysis, build_analysis_cursor)):
        # Compare the result statuses of the first and last analysis results.
        return
      else:
        break

    elif build_analysis_cursor.result_status in (
        wf_analysis_result_status.FOUND_UNTRIAGED,
        wf_analysis_result_status.FOUND_CORRECT_DUPLICATE,
        wf_analysis_result_status.FOUND_INCORRECT_DUPLICATE):
      # It is still within the continuous builds, not reach the end yet.
      if not _AnalysesForDuplicateFailures(
          first_build_analysis, build_analysis_cursor):
        # The build is not the same failure as the one we begin with
        # so it breaks the continuous serie of builds.
        return

      build_analyses.append(build_analysis_cursor)
      build_number_cursor += 1
      build_analysis_cursor = WfAnalysis.Get(
          master_name, builder_name, build_number_cursor)

    else:
      # If the build analysis' result_status is other status, such as
      # NOT_FOUND_CORRECT, there will be no continuous build failurs.
      return

  for build_analysis in build_analyses:
    if (first_build_analysis.result_status ==
        wf_analysis_result_status.FOUND_CORRECT):
      build_analysis.result_status = (
          wf_analysis_result_status.FOUND_CORRECT_DUPLICATE)
    else:
      build_analysis.result_status = (
          wf_analysis_result_status.FOUND_INCORRECT_DUPLICATE)
    build_analysis.put()


class CheckDuplicateFailures(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  @staticmethod
  def _FetchAndSortUntriagedAnalyses():
    query = WfAnalysis.query(
    WfAnalysis.result_status==wf_analysis_result_status.FOUND_UNTRIAGED)
    analyses = query.fetch()
    return sorted(
        analyses,
        key=lambda x : (x.master_name, x.builder_name, x.build_number))

  def HandleGet(self):
    """Checks the untriaged results and mark them as duplcates if they are."""
    analyses = CheckDuplicateFailures._FetchAndSortUntriagedAnalyses()

    for analysis in analyses:
      _ModifyStatusIfDuplicate(analysis)

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
