# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Pulls historical swarming task metadata from Findit and prints a report."""

from collections import defaultdict
from collections import OrderedDict
import datetime
import os
import sys

_REMOTE_API_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir)
sys.path.insert(1, _REMOTE_API_DIR)

import remote_api

from model import analysis_status
from model.wf_swarming_task import WfSwarmingTask


NOT_AVAILABLE = 'N/A'


# TODO(lijeffrey): Refactor helper methods into module sharable with
# try_job_data_query.py.
def _GetAverageOfNumbersInList(numbers):
  """Returns a float average of numbers or NOT_AVAILABLE if numbers is empty."""
  return (float(sum(numbers)) / len(numbers)) if numbers else NOT_AVAILABLE


def _FormatDigits(number):
  """Formats number into a 2-digit float, or NOT_AVAILABLE."""
  if isinstance(number, (int, float)):
    return float('%.2f' % number)
  return NOT_AVAILABLE


def _FormatSecondsAsHMS(seconds):
  """Formats the number of seconds into hours, minutes, seconds."""
  if seconds == NOT_AVAILABLE:
    return NOT_AVAILABLE

  minutes, seconds = divmod(seconds, 60)
  hours, minutes = divmod(minutes, 60)
  return '%d:%02d:%02d' % (hours, minutes, seconds)


def _FormatStepName(step_name):
  # Formats step_name to return only the first word (the step name itself).
  # Step names are expected to be in either the format 'step_name' or
  # 'step_name on platform'.
  return step_name.strip().split(' ')[0]


def _CategorizeSwarmingTaskData(swarming_task_list):
  """Categorizes swarming_task_list into a dict.

  Args:
    swarming_task_list: A list of WfSwarmingTask objects.

  Returns:
    A dict in the format:
    {
        priority1: {
            master_name1': {
                'builder_name1': {
                    'step_name1': [WfSwarmingTask1, WfSwarmingTask2, ...],
                    ...
                },
                ...
            },
            ...
        },
        ...
    }
  """
  categorized_data = defaultdict(
      lambda: defaultdict(
          lambda: defaultdict(
              lambda: defaultdict(list))))

  for swarming_task in swarming_task_list:
    if (not swarming_task.parameters or not swarming_task.tests_statuses or
        swarming_task.status != analysis_status.COMPLETED):
      # Disregard any swarming tasks that are not yet completed or were
      # triggered before 'parameters' and 'tests_statuses' were introduced.
      continue

    priority = swarming_task.parameters['priority']
    master_name = swarming_task.master_name
    builder_name = swarming_task.builder_name
    step_name = swarming_task.key.id()

    categorized_data[priority][master_name][builder_name][step_name].append(
        swarming_task)

  return categorized_data


def _GetReportInformation(swarming_task_list, start_date, end_date):
  """Computes and returns swarming task metadata in a dict.

  Args:
    swarming_task_list: A list of WfSwarmingTask entities.
    start_date: The earliest request date to compute data.
    end_date: The latest request date to compute data.

  Returns:
    A dict in the following format:
    {
        'swarming_tasks_per_day': The average number of swwarming tasks
            requested over the time period specified,
        'average_execution_time': The average amount of time spent on each
            swarming task not including in-queue time.
        'average_time_in_queue': The average amount of time a swarming task
            spends in-queue before it is picked up.
        'longest_execution_time': The length of time of the slowest swarming
            task in the period requested,
        'shortest_execution_time': The length of time of the fastest swarming
            task in the period requested.
        'tests_times_iterations': The number of tests multiplied by the number
            of iterations that test was run.
        'average_number_of_iterations': The average number of iterations each
            test for this step was run.
        'error_rate': The number of tasks that ended in error out of all tasks
            in swarming_task_list.
    }
  """
  swarming_tasks_per_day = NOT_AVAILABLE
  average_execution_time = NOT_AVAILABLE
  average_time_in_queue = NOT_AVAILABLE
  longest_execution_time = NOT_AVAILABLE
  shortest_execution_time = NOT_AVAILABLE
  average_number_of_iterations = NOT_AVAILABLE
  average_number_of_tests_run = NOT_AVAILABLE
  error_rate = NOT_AVAILABLE

  if swarming_task_list:
    task_count = len(swarming_task_list)
    swarming_tasks_per_day = task_count / float((end_date - start_date).days)
    execution_times_seconds = []
    in_queue_times = []
    iteration_counts = []
    tests_counts = []
    error_count = 0

    for swarming_task in swarming_task_list:
      # Execution time.
      if swarming_task.started_time and swarming_task.completed_time:
        execution_times_seconds.append(
            (swarming_task.completed_time - swarming_task.started_time).seconds)

      # In-queue time.
      if swarming_task.started_time and swarming_task.created_time:
        in_queue_times.append(
            (swarming_task.started_time - swarming_task.created_time).seconds)

      # Number of iterations.
      iterations_to_rerun = swarming_task.parameters.get(
          'iterations_to_rerun')
      if iterations_to_rerun is not None:
        iteration_counts.append(iterations_to_rerun)

      # Number of tests.
      number_of_tests = len(swarming_task.tests_statuses)
      if number_of_tests:
        tests_counts.append(number_of_tests)

      # Error rate.
      if swarming_task.status == analysis_status.ERROR:
        error_count += 1

    average_execution_time = (_GetAverageOfNumbersInList(
        execution_times_seconds) if execution_times_seconds else NOT_AVAILABLE)
    average_time_in_queue = (
        _GetAverageOfNumbersInList(in_queue_times) if in_queue_times else
        NOT_AVAILABLE)
    longest_execution_time = (
        str(datetime.timedelta(seconds=max(execution_times_seconds)))
        if execution_times_seconds else NOT_AVAILABLE)
    shortest_execution_time = (
        str(datetime.timedelta(seconds=min(execution_times_seconds)))
        if execution_times_seconds else NOT_AVAILABLE)
    average_number_of_iterations = _GetAverageOfNumbersInList(iteration_counts)
    average_number_of_tests_run = _GetAverageOfNumbersInList(tests_counts)
    tests_times_iterations = (
        average_number_of_iterations * average_number_of_tests_run)
    error_rate = error_count / task_count

  return {
      'swarming_tasks_per_day': swarming_tasks_per_day,
      'average_execution_time': average_execution_time,
      'average_time_in_queue': average_time_in_queue,
      'longest_execution_time': longest_execution_time,
      'shortest_execution_time': shortest_execution_time,
      'tests_times_iterations': tests_times_iterations,
      'average_number_of_iterations': average_number_of_iterations,
      'average_number_of_tests_run': average_number_of_tests_run,
      'error_rate': error_rate
  }


def _GetReport(categorized_swarming_task_dict, start_date, end_date):
  """Returns a swarming task data report as an ordered dict sorted by priority.

  Args:
    categorized_swarming_task_dict: A dict categorizing WFSwarmingTask entities
      organized by priority, master_name, builder_name, step_name. This dict
      should be the output from _CategorizeSwarmingTaskData().
    start_date: The earliest request date for which data should be computed.
    end_date: The latest request date for which data should be computed.

  Returns:
    An ordered dict by highest priority (lower priority number) swarming tasks
      in the format:
      {
          priority: {
              'master_name': {
                  'builder_name': {
                      'step_name': {
                          'swarming_tasks_per_day': number or 'N/A',
                          'average_execution_time': number or 'N/A',
                          'average_time_in_queue': number or 'N/A',
                          'longest_execution_time': number or 'N/A',
                          'shortest_execution_time': number or 'N/A',
                          'tests_times_iterations': number or 'N/A'
                          'average_number_of_tests_run': number or 'N/A',
                          'average_number_of_iterations': number or 'N/A',
                          'error_rate': number or 'N/A'
                      },
                      ...
                  },
                  ...
              },
              ...
          },
          ...
      }
  """
  report = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

  for priority, masters in categorized_swarming_task_dict.iteritems():
    for master, builders in masters.iteritems():
      for builder, steps in builders.iteritems():
        for step, swarming_task_data_list in steps.iteritems():
          report[priority][master][builder][step] = _GetReportInformation(
              swarming_task_data_list, start_date, end_date)

  return OrderedDict(sorted(report.items()))


def CreateHtmlPage(report, start_date, end_date):
  """Generates an html string for displaying the report.

  Args:
    report: A dict containing all the relevant information returned from
      _GetReport().
    start_date: The earliest date that a swarming task was requested.
    end_date: The latest date that a swarming task was requested.

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
  html += '<b>Swarming task metadata from %s to %s (%s days)</b>' % (
      str(start_date), str(end_date), (end_date - start_date).days)
  html += '<h1>Aggregate metadata for swarming tasks by priority</h1>'

  cell_template = '<td>%s</td>'

  for priority, masters in report.iteritems():
    html += '<h2>Task Priority: %s</h2>' % priority
    html += """
      <table>
      <tr>
        <th>Master</th>
        <th>Builder</th>
        <th>Step</th>
        <th>Average # Tasks Per Day</th>
        <th>Average Time In Queue</th>
        <th>Average Execution Time</th>
        <th>Longest Execution Time</th>
        <th>Shortest Execution Time</th>
        <th># Tests * # Iterations</th>
        <th>Average # Iterations</th>
        <th>Average # Tests Run</th>
        <th>Error Rate</th>
      </tr>"""

    for master_name, builder_reports in masters.iteritems():
      for builder_name, steps in builder_reports.iteritems():
        for step_name in steps:
          builder_report = (
              report[priority][master_name][builder_name][step_name])

          html += '<tr>'
          html += cell_template % master_name
          html += cell_template % builder_name
          html += cell_template % _FormatStepName(step_name)
          html += cell_template % _FormatDigits(
              builder_report['swarming_tasks_per_day'])
          html += cell_template % _FormatSecondsAsHMS(_FormatDigits(
              builder_report['average_time_in_queue']))
          html += cell_template % _FormatSecondsAsHMS(_FormatDigits(
              builder_report['average_execution_time']))
          html += cell_template % builder_report['longest_execution_time']
          html += cell_template % builder_report['shortest_execution_time']
          html += cell_template % _FormatDigits(
              builder_report['tests_times_iterations'])
          html += cell_template % _FormatDigits(
              builder_report['average_number_of_iterations'])
          html += cell_template % _FormatDigits(
              builder_report['average_number_of_tests_run'])
          html += cell_template % _FormatDigits(builder_report['error_rate'])

    html += '</table>'

  return html


if __name__ == '__main__':
  # Set up the Remote API to use services on the live App Engine.
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  START_DATE = datetime.datetime(2016, 2, 1)
  END_DATE = datetime.datetime(2016, 3, 7)

  wf_analysis_query = WfSwarmingTask.query(
      WfSwarmingTask.created_time >= START_DATE,
      WfSwarmingTask.created_time < END_DATE)
  data_list = wf_analysis_query.fetch()

  categorized_data_dict = _CategorizeSwarmingTaskData(data_list)
  final_report = _GetReport(categorized_data_dict, START_DATE, END_DATE)

  findit_tmp_dir = os.environ.get('TMP_DIR')
  if not findit_tmp_dir:
    findit_tmp_dir = os.getcwd()

  report_path = os.path.join(findit_tmp_dir,
                             'swarming_task_metadata_report.html')

  with open(report_path, 'w') as f:
    f.write(CreateHtmlPage(final_report, START_DATE, END_DATE))

  print 'Swarming task metadata report available at file://%s' % report_path
