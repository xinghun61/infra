# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Pulls historical try job metadata from Findit and prints a report."""

import argparse
from collections import defaultdict
import datetime
import json
import numpy
import os
import sys

try:
  from matplotlib import pyplot
except ImportError:
  pyplot = None

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)
from local_libs import remote_api

from model.wf_try_job_data import WfTryJobData

NOT_AVAILABLE = 'N/A'


def _GetOSPlatformName(master_name, builder_name):
  """Returns the OS platform name based on the master and builder."""
  builder_name = builder_name.lower()
  master_name = master_name.lower()

  if master_name == 'chromium.win':
    return 'win'
  elif master_name == 'chromium.linux':
    if 'android' in builder_name:
      return 'android'
    else:
      return 'unix'
  elif master_name == 'chromium.chromiumos':
    return 'unix'
  else:
    os_map = {
        'win': 'win',
        'linux': 'unix',
        'chromiumos': 'unix',
        'chromeos': 'unix',
        'android': 'android',
        'mac': 'mac',
        'ios': 'ios',
    }

    for os_name, platform in os_map.iteritems():
      if os_name in builder_name:
        return platform

    return 'unknown'


def _GetTrybotName(buildbucket_response):
  # First try parameters_json.
  parameters = json.loads(buildbucket_response.get('parameters_json', '{}'))
  trybot = parameters.get('builder_name')

  if not trybot:
    # Fallback to response_details_json.
    response_details = json.loads(
        buildbucket_response.get('response_details_json', '{}'))
    properties = response_details.get('properties', {})
    trybot = properties.get('buildername')

    if not trybot:
      trybot = 'unknown'

  return trybot


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


def _GetRequestSpikes(request_times,
                      time_window_seconds=30 * 60,
                      minimum_spike_size=3,
                      show_plot=False):
  """Calculates and plots try jobs by request time.

  Args:
    request_time: List of datetime objects representing try job request times.
    time_window_seconds: Maximum number of seconds between requests to count
      as a spike.
    minimum_spike_size: Minimum number of requests within the specified time
      window needed to count as a spike.
    show_plot: Boolean whether to display visual graphs of the request times.

  Returns:
    spike_count: The number of spikes found.
    average_spike_size: The average number of requests in each spike.
    maximum_spike_size: The number of requests in the biggest spike.
  """
  request_times = sorted(request_times)

  if show_plot:
    if pyplot:
      pyplot.plot(request_times, [i for i in range(len(request_times))], 'x')
      pyplot.show()
    else:
      print('In order to show plots, matplotlib needs to be installed. To '
            'install, please run \'sudo pip install matplotlib\'')

  candidate_spike_start = request_times[0]
  points_in_spike = 1
  spike_count = 0
  spike_sizes = []

  for point_being_examined in request_times[1:]:
    if ((point_being_examined - candidate_spike_start).total_seconds() <
        time_window_seconds):
      points_in_spike += 1
    else:
      # The time window has passed. Need a new starting point.
      if points_in_spike >= minimum_spike_size:
        spike_count += 1
        spike_sizes.append(points_in_spike)

      candidate_spike_start = point_being_examined
      points_in_spike = 1  # Start over.

  return (spike_count, _GetAverageOfNumbersInList(spike_sizes), max(spike_sizes)
          if spike_sizes else 0)


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
        'time_per_revision': The average amount of execution time spent on each
            revision.
        'under_five_minutes_rate': The number of try jobs that finished under 5
            minutes / total try jobs.
        'under_fifteen_minutes_rate': The number of try jobs that finished in
            under 15 minutes / total try jobs.
        'under_thirty_minutes_rate': The number of try jobs that finished in
            under 30 minutes / total try jobs.
        'over_thirty_minutes_rate': The number of try jobs that finished in over
            30 minutes / total try jobs.
    }
  """
  try_jobs_per_day = NOT_AVAILABLE
  average_regression_range_size = NOT_AVAILABLE
  median_regression_range_size = NOT_AVAILABLE
  average_execution_time = NOT_AVAILABLE
  median_execution_time = NOT_AVAILABLE
  average_end_to_end_time = NOT_AVAILABLE
  median_end_to_end_time = NOT_AVAILABLE
  average_time_in_queue = NOT_AVAILABLE
  median_execution_time = NOT_AVAILABLE
  average_commits_analyzed = NOT_AVAILABLE
  median_commits_analyzed = NOT_AVAILABLE
  longest_execution_time = NOT_AVAILABLE
  shortest_execution_time = NOT_AVAILABLE
  detection_rate = NOT_AVAILABLE
  error_rate = NOT_AVAILABLE
  number_of_try_jobs = len(try_job_data_list) if try_job_data_list else 0
  time_per_revision = NOT_AVAILABLE
  under_five_minutes_rate = NOT_AVAILABLE
  under_fifteen_minutes_rate = NOT_AVAILABLE
  under_thirty_minutes_rate = NOT_AVAILABLE
  over_thirty_minutes_rate = NOT_AVAILABLE
  spike_count = NOT_AVAILABLE
  average_spike_size = NOT_AVAILABLE
  maximum_spike_size = NOT_AVAILABLE

  if try_job_data_list:
    try_jobs_per_day = (len(try_job_data_list) / float(
        (end_date - start_date).days))
    regression_range_sizes = []
    execution_times_seconds = []
    request_times = []
    in_queue_times = []
    end_to_end_times = []
    commits_analyzed = []
    culprits_detected = 0
    errors_detected = 0
    number_under_five_minutes = 0
    number_under_fifteen_minutes = 0
    number_under_thirty_minutes = 0
    number_over_thirty_minutes = 0
    total_number_of_try_jobs = len(try_job_data_list)

    for try_job_data in try_job_data_list:
      # Regression range size.
      if try_job_data.regression_range_size:
        regression_range_sizes.append(try_job_data.regression_range_size)

      # Execution time.
      if try_job_data.start_time and try_job_data.end_time:
        execution_time_delta = (try_job_data.end_time - try_job_data.start_time)
        execution_time = execution_time_delta.total_seconds()
        execution_times_seconds.append(execution_time)

      # In-queue time.
      if try_job_data.start_time and try_job_data.request_time:
        in_queue_time_delta = (
            try_job_data.start_time - try_job_data.request_time)
        in_queue_time = in_queue_time_delta.total_seconds()
        in_queue_times.append(in_queue_time)

      # Total time end-to-end.
      if try_job_data.request_time:
        request_times.append(try_job_data.request_time)

        if try_job_data.end_time:
          total_time_delta = try_job_data.end_time - try_job_data.start_time
          total_time_seconds = total_time_delta.total_seconds()
          end_to_end_times.append(total_time_seconds)

          if total_time_seconds < 300:  # Under 5 minutes.
            number_under_five_minutes += 1
          elif total_time_seconds < 900:  # Under 15 minutes.
            number_under_fifteen_minutes += 1
          elif total_time_seconds < 1800:  # Under 30 minutes.
            number_under_thirty_minutes += 1
          else:  # Over 30 minutes.
            number_over_thirty_minutes += 1

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
    median_regression_range_size = (numpy.median(regression_range_sizes) if
                                    regression_range_sizes else NOT_AVAILABLE)
    average_execution_time = (
        _GetAverageOfNumbersInList(execution_times_seconds)
        if execution_times_seconds else NOT_AVAILABLE)
    median_execution_time = (numpy.median(execution_times_seconds)
                             if execution_times_seconds else NOT_AVAILABLE)
    average_end_to_end_time = (_GetAverageOfNumbersInList(end_to_end_times)
                               if end_to_end_times else NOT_AVAILABLE)
    median_end_to_end_time = (numpy.median(end_to_end_times)
                              if end_to_end_times else NOT_AVAILABLE)
    average_time_in_queue = (_GetAverageOfNumbersInList(in_queue_times)
                             if in_queue_times else NOT_AVAILABLE)
    median_time_in_queue = (numpy.median(in_queue_times)
                            if in_queue_times else NOT_AVAILABLE)
    average_commits_analyzed = _GetAverageOfNumbersInList(commits_analyzed)
    median_commits_analyzed = (numpy.median(commits_analyzed)
                               if commits_analyzed else NOT_AVAILABLE)
    longest_execution_time = (str(
        datetime.timedelta(seconds=int(round(max(execution_times_seconds)))))
                              if execution_times_seconds else NOT_AVAILABLE)
    shortest_execution_time = (str(
        datetime.timedelta(seconds=int(round(min(execution_times_seconds)))))
                               if execution_times_seconds else NOT_AVAILABLE)
    detection_rate = float(culprits_detected) / total_number_of_try_jobs
    error_rate = float(errors_detected) / total_number_of_try_jobs
    time_per_revision = (average_execution_time / average_commits_analyzed
                         if (average_execution_time != NOT_AVAILABLE and
                             average_commits_analyzed != NOT_AVAILABLE) else
                         NOT_AVAILABLE)

    under_five_minutes_rate = (
        float(number_under_five_minutes) / total_number_of_try_jobs)
    under_fifteen_minutes_rate = (
        float(number_under_fifteen_minutes) / total_number_of_try_jobs)
    under_thirty_minutes_rate = (
        float(number_under_thirty_minutes) / total_number_of_try_jobs)
    over_thirty_minutes_rate = (
        float(number_over_thirty_minutes) / total_number_of_try_jobs)

    # Calculate try job spikes.
    spike_count, average_spike_size, maximum_spike_size = _GetRequestSpikes(
        request_times,
        time_window_seconds=30 * 60,
        minimum_spike_size=3,
        show_plot=False)

  return {
      'try_jobs_per_day':
          _FormatDigits(try_jobs_per_day),
      'average_regression_range_size':
          _FormatDigits(average_regression_range_size),
      'median_regression_range_size':
          median_regression_range_size,
      'average_execution_time':
          _FormatSecondsAsHMS(_FormatDigits(average_execution_time)),
      'median_execution_time':
          _FormatSecondsAsHMS(_FormatDigits(median_execution_time)),
      'average_end_to_end_time':
          _FormatSecondsAsHMS(_FormatDigits(average_end_to_end_time)),
      'median_end_to_end_time':
          _FormatSecondsAsHMS(_FormatDigits(median_end_to_end_time)),
      'average_time_in_queue':
          _FormatSecondsAsHMS(_FormatDigits(average_time_in_queue)),
      'median_time_in_queue':
          _FormatSecondsAsHMS(_FormatDigits(median_time_in_queue)),
      'average_commits_analyzed':
          _FormatDigits(average_commits_analyzed),
      'median_commits_analyzed':
          median_commits_analyzed,
      'longest_execution_time':
          longest_execution_time,
      'shortest_execution_time':
          shortest_execution_time,
      'number_of_try_jobs':
          number_of_try_jobs,
      'detection_rate':
          _FormatDigits(detection_rate),
      'error_rate':
          _FormatDigits(error_rate),
      'time_per_revision':
          _FormatSecondsAsHMS(_FormatDigits(time_per_revision)),
      'under_five_minutes_rate':
          _FormatDigits(under_five_minutes_rate),
      'under_fifteen_minutes_rate':
          _FormatDigits(under_fifteen_minutes_rate),
      'under_thirty_minutes_rate':
          _FormatDigits(under_thirty_minutes_rate),
      'over_thirty_minutes_rate':
          _FormatDigits(over_thirty_minutes_rate),
      'request_spike_count':
          spike_count,
      'request_spike_average_size':
          average_spike_size,
      'request_spike_maximum_size':
          maximum_spike_size,
  }


def PrintCommonStats(try_job_data_list, start_date, end_date, indent):
  """Takes a list of WfTryJobData entities and prints their stats."""
  spaces = ''
  for _ in range(indent):
    spaces += ' '

  report_info = _GetReportInformation(try_job_data_list, start_date, end_date)
  for key, value in report_info.iteritems():
    print '%s%s: %s' % (spaces, key, value)


def PrettyPrint(grouped_data, start_date, end_date, indent=0):
  if not grouped_data:
    return
  if isinstance(grouped_data, list):
    # Print the stats about the list.
    PrintCommonStats(grouped_data, start_date, end_date, indent)
  elif isinstance(grouped_data, dict):
    spaces = ''
    for _ in range(indent):
      spaces += ' '

    for field, data in grouped_data.iteritems():
      print spaces + field
      PrettyPrint(data, start_date, end_date, indent + 2)
  else:
    raise Exception('grouped_data dict should only contain dicts or lists.')


def _SplitListByTryJobType(try_job_data_list):
  categorized_data_dict = {'compile': [], 'test': []}
  for try_job_data in try_job_data_list:
    if try_job_data.try_job_type.lower() == 'compile':
      categorized_data_dict['compile'].append(try_job_data)
    elif try_job_data.try_job_type.lower() == 'test':
      categorized_data_dict['test'].append(try_job_data)

  return categorized_data_dict


def _SplitListByMaster(try_job_data_list):
  categorized_data_dict = defaultdict(list)

  for try_job_data in try_job_data_list:
    master_name = try_job_data.master_name

    if not master_name:
      continue

    categorized_data_dict[master_name].append(try_job_data)

  return categorized_data_dict


def _SplitListByBuilder(try_job_data_list):
  categorized_data_dict = defaultdict(list)

  for try_job_data in try_job_data_list:
    builder_name = try_job_data.builder_name

    if not builder_name:
      continue

    categorized_data_dict[builder_name].append(try_job_data)

  return categorized_data_dict


def _SplitListByHeuristicResults(try_job_data_list):
  categorized_data_dict = {
      'with heuristic guidance': [],
      'without heuristic guidance': []
  }
  for try_job_data in try_job_data_list:
    if try_job_data.has_heuristic_results:
      categorized_data_dict['with heuristic guidance'].append(try_job_data)
    else:
      categorized_data_dict['without heuristic guidance'].append(try_job_data)
  return categorized_data_dict


def _SplitListByCompileTargets(try_job_data_list):
  categorized_data_dict = {
      'with compile targets': [],
      'without compile targets': []
  }
  for try_job_data in try_job_data_list:
    if try_job_data.has_compile_targets:
      categorized_data_dict['with compile targets'].append(try_job_data)
    else:
      categorized_data_dict['without compile targets'].append(try_job_data)
  return categorized_data_dict


def _SplitListByError(try_job_data_list):
  categorized_data_dict = {'with error': [], 'without error': []}
  for try_job_data in try_job_data_list:
    if try_job_data.error:
      categorized_data_dict['with error'].append(try_job_data)
    else:
      categorized_data_dict['without error'].append(try_job_data)
  return categorized_data_dict


def _SplitListByPlatform(try_job_data_list):
  categorized_data_dict = defaultdict(list)

  for try_job_data in try_job_data_list:
    builder_name = try_job_data.builder_name
    master_name = try_job_data.master_name

    if not master_name or not builder_name:
      continue

    platform = _GetOSPlatformName(master_name, builder_name)
    categorized_data_dict[platform].append(try_job_data)

  return categorized_data_dict


def _SplitListByTrybot(try_job_data_list):
  categorized_data_dict = defaultdict(list)

  for try_job_data in try_job_data_list:
    if not try_job_data.last_buildbucket_response:
      continue

    trybot = _GetTrybotName(try_job_data.last_buildbucket_response)
    categorized_data_dict[trybot].append(try_job_data)

  return categorized_data_dict


def SplitListByOption(try_job_data_list, option):
  """Takes a WfTryJobData list and separates it into a dict based on arg.

  Args:
    try_job_data_list: A list of WfTryJobData entities.
    option: An option with which to split the data by.

  Returns:
    A dict where the keys are how the data is separated based on arg and the
    values are the corresponding lists of data.
  """

  if option == 'b':  # Main waterfall builder.
    return _SplitListByBuilder(try_job_data_list)
  elif option == 'c':  # Whether or not compile targets are included.
    return _SplitListByCompileTargets(try_job_data_list)
  elif option == 'e':  # Whether or not try jobs with errors should be counted.
    return _SplitListByError(try_job_data_list)
  elif option == 'm':  # Main waterfall master.
    return _SplitListByMaster(try_job_data_list)
  elif option == 'p':  # Split by OS platform.
    return _SplitListByPlatform(try_job_data_list)
  elif option == 'r':  # Whether or not heuristic results are included.
    return _SplitListByHeuristicResults(try_job_data_list)
  elif option == 't':  # Try job type.
    return _SplitListByTryJobType(try_job_data_list)
  elif 'trybot' in option:  # Split by trybot.
    return _SplitListByTrybot(try_job_data_list)

  # Unsupported flag, bail out without modification.
  return try_job_data_list


def SplitStructByOption(try_job_data_struct, option):
  if isinstance(try_job_data_struct, list):
    try_job_data_struct = SplitListByOption(try_job_data_struct, option)
  elif isinstance(try_job_data_struct, dict):
    for key, struct in try_job_data_struct.iteritems():
      try_job_data_struct[key] = SplitStructByOption(struct, option)
  else:
    raise Exception('try job data dict must only contain lists or dicts.')

  return try_job_data_struct


def GetArgsInOrder():
  command_line_args = sys.argv[1:]

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-b', action='store_true', help='group try job data by builder')
  parser.add_argument(
      '-c',
      action='store_true',
      help=('group try job data by those with and without '
            'compile targets'))
  parser.add_argument(
      '-e',
      action='store_true',
      help=('group try job data by those with and without '
            'errors detected'))
  parser.add_argument(
      '-m', action='store_true', help='group try job data by master')
  parser.add_argument(
      '-p', action='store_true', help='group try job data by platform')
  parser.add_argument(
      '-r',
      action='store_true',
      help=('group try job data by those with and without '
            'heuristic results'))
  parser.add_argument(
      '-t',
      action='store_true',
      help='group try job data by type (compile, test)')
  parser.add_argument(
      '--trybot', action='store_true', help='group try job data by trybot')

  args_dict = vars(parser.parse_args())

  # Preserve order from original command.
  ordered_args = []

  for original_arg in command_line_args:
    parsed_arg = original_arg.lstrip('-')
    if args_dict[parsed_arg]:
      ordered_args.append(parsed_arg)

  return ordered_args


if __name__ == '__main__':
  # Set up the Remote API to use services on the live App Engine.
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  START_DATE = datetime.datetime(2016, 4, 17)
  END_DATE = datetime.datetime(2016, 7, 15)

  try_job_data_query = WfTryJobData.query(
      WfTryJobData.request_time >= START_DATE,
      WfTryJobData.request_time < END_DATE)
  categorized_data = try_job_data_query.fetch()

  args = GetArgsInOrder()
  for arg in args:
    categorized_data = SplitStructByOption(categorized_data, arg)

  # TODO(lijeffrey): Display data in an html page instead of printing.
  PrettyPrint(categorized_data, START_DATE, END_DATE)
