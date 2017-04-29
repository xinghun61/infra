# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Pulls historical try job metadata from Findit and prints a report."""

from collections import defaultdict
import datetime
import os
import sys

_FINDIT_DIR = os.path.join(os.path.dirname(__file__),
                           os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)
from local_libs import remote_api

from model.wf_config import FinditConfig
from model.wf_try_job_data import WfTryJobData


NOT_AVAILABLE = 'N/A'


def _GetAverageOfNumbersInList(numbers):
  """Returns a float average of numbers or NOT_AVAILABLE if numbers is empty."""
  return (float(sum(numbers)) / len(numbers)) if numbers else NOT_AVAILABLE


def _FormatDigits(number):
  """Formats number into a 2-digit float, or NOT_AVAILABLE."""
  if isinstance(number, float):
    return float('%.2f' % number)
  return NOT_AVAILABLE


def _FormatSecondsAsHMS(seconds):
  """Formats the number of seconds into hours, minutes, seconds."""
  if seconds == NOT_AVAILABLE:
    return NOT_AVAILABLE

  minutes, seconds = divmod(seconds, 60)
  hours, minutes = divmod(minutes, 60)
  return '%d:%02d:%02d' % (hours, minutes, seconds)


def _CategorizeTryJobData(try_job_data_list):
  """Categorizes try_job_data_list into a dict.

  Args:
    try_job_data_list: A list of WfTryJobData objects.

  Returns:
    A dict in the format:
    {
        'compile': {
            'master_name1': {
                'builder_name1': [WfTryJobData1, WfTryJobData2, ...],
                'builder_name2': [WfTryJobData3, ...]
            },
            'master_name2: {
                ...
            }
        },
        'test': {
           ...
        }
    }
  """
  categorized_data = {
      'compile': defaultdict(lambda: defaultdict(list)),
      'test': defaultdict(lambda: defaultdict(list))
  }

  for try_job_data in try_job_data_list:
    master_name = try_job_data.master_name
    builder_name = try_job_data.builder_name

    if not master_name or not builder_name:
      continue

    try_job_type = try_job_data.try_job_type

    categorized_data[try_job_type][master_name][builder_name].append(
        try_job_data)

  return categorized_data


def _GetReportInformation(try_job_data_list, start_date, end_date):
  """Computes and returns try job metadata.

  Args:
    try_job_data_list: A list of WfTryJobData entities.
    start_date: The earliest request date to compute data.
    end_date: The latest request date to compute data.

  Returns:
    A dict in the following format:
    {
        'try_jobs_per_day': The average number of jobs requested over the time
            period specified,
        'average_regression_range_size': The average number of revisions in the
            regression range when the original failure was detected,
        'average_execution_time': The average amount of time spent on each try
            job not including in-queue time.
        'average_time_in_queue': The average amount of time a try job spends
            in-queue before it is picked up.
        'average_commits_analyzed': The average number of revisions each try job
            needed to run before coming to a conclusion,
        'longest_execution_time': The length of time of the slowest try job,
        'shortest_execution_time': The length of time of the fastest try job,
        'number_of_try_jobs': The number of try jobs in this list,
        'detection_rate': The number of try jobs that found any culprits at all
            regardless of correctness over the total number of try jobs.
        'error_rate': The number of try jobs that had an error / the total
            number of try jobs in the list.
    }
  """
  try_jobs_per_day = NOT_AVAILABLE
  average_regression_range_size = NOT_AVAILABLE
  average_execution_time = NOT_AVAILABLE
  average_time_in_queue = NOT_AVAILABLE
  average_commits_analyzed = NOT_AVAILABLE
  longest_execution_time = NOT_AVAILABLE
  shortest_execution_time = NOT_AVAILABLE
  detection_rate = NOT_AVAILABLE
  error_rate = NOT_AVAILABLE
  number_of_try_jobs = len(try_job_data_list) if try_job_data_list else 0

  if try_job_data_list:
    try_jobs_per_day = (
        len(try_job_data_list) / float((end_date - start_date).days))
    regression_range_sizes = []
    execution_times_seconds = []
    in_queue_times = []
    commits_analyzed = []
    culprits_detected = 0
    errors_detected = 0

    for try_job_data in try_job_data_list:
      # Regression range size.
      if try_job_data.regression_range_size:
        regression_range_sizes.append(try_job_data.regression_range_size)

      # Execution time.
      if try_job_data.start_time and try_job_data.end_time:
        execution_times_seconds.append(
            (try_job_data.end_time - try_job_data.start_time).seconds)

      # In-queue time.
      if try_job_data.start_time and try_job_data.request_time:
        in_queue_times.append(
            (try_job_data.start_time - try_job_data.request_time).seconds)

      # Number of commits analyzed.
      if try_job_data.number_of_commits_analyzed:
        commits_analyzed.append(try_job_data.number_of_commits_analyzed)

      # Culprit detection rate.
      if try_job_data.culprits:
        culprits_detected += 1

      if try_job_data.error:
        errors_detected += 1

    average_regression_range_size = _GetAverageOfNumbersInList(
        regression_range_sizes)
    average_execution_time = (_GetAverageOfNumbersInList(
        execution_times_seconds) if execution_times_seconds else NOT_AVAILABLE)
    average_time_in_queue = (
        _GetAverageOfNumbersInList(in_queue_times) if in_queue_times else
        NOT_AVAILABLE)
    average_commits_analyzed = _GetAverageOfNumbersInList(
        commits_analyzed)
    longest_execution_time = (
        str(datetime.timedelta(seconds=max(execution_times_seconds)))
        if execution_times_seconds else NOT_AVAILABLE)
    shortest_execution_time = (
        str(datetime.timedelta(seconds=min(execution_times_seconds)))
        if execution_times_seconds else NOT_AVAILABLE)
    detection_rate = float(culprits_detected) / len(try_job_data_list)
    error_rate = float(errors_detected) / len(try_job_data_list)

  return {
      'try_jobs_per_day': try_jobs_per_day,
      'average_regression_range_size': average_regression_range_size,
      'average_execution_time': average_execution_time,
      'average_time_in_queue': average_time_in_queue,
      'average_commits_analyzed': average_commits_analyzed,
      'longest_execution_time': longest_execution_time,
      'shortest_execution_time': shortest_execution_time,
      'number_of_try_jobs': number_of_try_jobs,
      'detection_rate': detection_rate,
      'error_rate': error_rate
  }


def _GetReportListForMastersAndBuilders(supported_masters_to_builders,
                                        categorized_data_dict,
                                        start_date, end_date):
  """Gets a full try job data report of each master and builder.

  Args:
    supported_masters_to_builders: Findit's config for mapping masters to
      builders.
    categorized_data_dict: A dict mapping try job types to masters, masters to
      builders, and builders to lists of WfTryJobData objects. This dict should
      be the output of _CategorizeTryJobData().
    start_date: The earliest request date for which data should be computed.
    end_date: The latest request date for which data should be computed.

  Returns:
    A list of dicts of masters to builders, with the metadata associated with
    each builder based on the data provided in all_try_job_data_list in the
    format [supported_dict, unsupported_dict]. All supported masters and
    builders are accounted for even if there is no data, and all available data
    is displayed even if support for it has been deprecated.
    [
        {
            'compile': {
                'master_name': {
                    'builder_name': {
                        'try_jobs_per_day': 1 or 'N/A',
                        'average_regression_range_size': 1 or 'N/A',
                        'average_execution_time': 1 or 'N/A',
                        'average_time_in_queue': 1 or 'N/A',
                        'average_commits_analyzed': 1 or 'N/A',
                        'longest_execution_time': 1 or 'N/A',
                        'shortest_execution_time': 1 or 'N/A',
                        'number_of_try_jobs': 1 or 'N/A',
                        'detection_rate': 0.0-1.0 or 'N/A',
                        'error_rate': 0.0-1.0 or 'N/A'
                    },
                    ...
                },
            },
            'test': {
                ....
            }
          ...
        },
        {
            'compile': ...,
            'test': ...
        }
    ]
  """
  supported = defaultdict(dict)
  unsupported = defaultdict(dict)
  report = [supported, unsupported]

  # Build the supported report according to Findit's config.
  for master, builders in supported_masters_to_builders.iteritems():
    supported['compile'][master] = {}
    supported['test'][master] = {}

    for builder in builders:
      compile_try_job_data_list = (
          categorized_data_dict.get('compile').get(master, {}).get(builder))
      test_try_job_data_list = (
          categorized_data_dict.get('test').get(master, {}).get(builder))
      supported['compile'][master][builder] = _GetReportInformation(
          compile_try_job_data_list, start_date, end_date)
      supported['test'][master][builder] = _GetReportInformation(
          test_try_job_data_list, start_date, end_date)

  # Build the unsupported report according to what's in the try job data list
  # but not found in Findit's config.
  for try_job_type, try_job_data_dict in categorized_data_dict.iteritems():
    for master, builders in try_job_data_dict.iteritems():
      unsupported[try_job_type][master] = {}

      for builder in builders:
        if not supported_masters_to_builders.get(master, {}).get(builder):
          try_job_data_list = (
              categorized_data_dict[try_job_type][master][builder])
          unsupported[try_job_type][master][builder] = _GetReportInformation(
              try_job_data_list, start_date, end_date)

  return report


def CreateHtmlPage(report_list, start_date, end_date):
  """Generates an html string for displaying the report.

  Args:
    report_list: A list of 2 report dicts. The first is expected to contain data
      for masters and builders that are supported as specified by Findit's
      config at the time that this script is run. The second is for data that is
      found but not supported.
    start_date: The earliest date that a try job was requested to be reported.
    end_date: The latest date that a try job was requested to be reported.

  Returns:
    A string containing the html body for the final report page.
  """
  html = """
      <style>
        table {
          border-collapse: collapse;
          border: 1px solid gray;
        }
        table td, th {
          border: 1px solid gray;
        }
      </style>"""

  html += '<b>Try job metadata from %s to %s (%s days)</b>' % (
      str(start_date), str(end_date), (end_date - start_date).days)
  html += '<h1>Aggregate metadata for try jobs per master/builder</h1>'

  for i in range(len(report_list)):
    if i == 0:  # Supported dict.
      html += '<h2>Supported Masters/Builders</h2>'
      cell_template = '<td>%s</td>'
    else:  # Unsupported dict.
      html += '<h2>Unsupported Masters/Builders</h2>'
      cell_template = '<td bgcolor="#CCCCCC">%s</td>'

    report = report_list[i]
    for try_job_type, try_job_report in report.iteritems():
      html += '<h3>Try job type: %s</h3>' % try_job_type
      html += """
        <table>
          <tr>
            <th>Master</th>
            <th>Builder</th>
            <th># Try Jobs Per Day</th>
            <th>Average Regression Range Size</th>
            <th>Average # Revisions Analyzed</th>
            <th>Average Time In Queue</th>
            <th>Average Execution Time</th>
            <th>Longest Execution Time</th>
            <th>Shortest Execution Time</th>
            <th>Culprit Detection Rate</th>
            <th># Try Jobs</th>
            <th>Error Rate</th>
          </tr>"""

      for master_name, builder_reports in try_job_report.iteritems():
        for builder_name in builder_reports:
          builder_report = report[try_job_type][master_name][builder_name]
          html += '<tr>'
          html += cell_template % master_name
          html += cell_template % builder_name
          html += cell_template % _FormatDigits(
              builder_report['try_jobs_per_day'])
          html += cell_template % _FormatDigits(
              builder_report['average_regression_range_size'])
          html += cell_template % _FormatDigits(
              builder_report['average_commits_analyzed'])
          html += cell_template % _FormatSecondsAsHMS(_FormatDigits(
              builder_report['average_time_in_queue']))
          html += cell_template % _FormatSecondsAsHMS(_FormatDigits(
              builder_report['average_execution_time']))
          html += cell_template % builder_report['longest_execution_time']
          html += cell_template % builder_report['shortest_execution_time']
          html += cell_template % _FormatDigits(
              builder_report['detection_rate'])
          html += cell_template % builder_report['number_of_try_jobs']
          html += cell_template % _FormatDigits(builder_report['error_rate'])
          html += '</tr>'

      html += '</table>'

  return html


if __name__ == '__main__':
  # Set up the Remote API to use services on the live App Engine.
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  START_DATE = datetime.datetime(2016, 3, 1)
  END_DATE = datetime.datetime(2016, 4, 14)

  wf_analysis_query = WfTryJobData.query(
      WfTryJobData.request_time >= START_DATE,
      WfTryJobData.request_time < END_DATE)
  data_list = wf_analysis_query.fetch()

  masters_to_builders = FinditConfig.Get().builders_to_trybots
  data = _CategorizeTryJobData(data_list)
  full_report_list = _GetReportListForMastersAndBuilders(
      masters_to_builders, data, START_DATE, END_DATE)

  findit_tmp_dir = os.environ.get('TMP_DIR')
  if not findit_tmp_dir:
    findit_tmp_dir = os.getcwd()

  report_path = os.path.join(findit_tmp_dir, 'try_job_data_report.html')

  with open(report_path, 'w') as f:
    f.write(CreateHtmlPage(full_report_list, START_DATE, END_DATE))

  print 'Try job metadata report available at file://%s' % report_path
