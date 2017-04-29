# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Pulls Findit data and outputs minutes between analyses."""

from collections import Counter
from collections import defaultdict
import datetime
import json
import numpy
import os
import pickle
import sys

_APPENGINE_SDK_DIR = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                  os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir,
                                  'google_appengine')
sys.path.insert(1, _APPENGINE_SDK_DIR)

from google.appengine.ext import ndb

_FINDIT_DIR = os.path.join(os.path.dirname(__file__),
                           os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)
from local_libs import remote_api

from common.waterfall import failure_type
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild


NOT_AVAILABLE = 'N/A'
START_DATE = datetime.datetime(2016, 1, 1)
END_DATE = datetime.datetime(2016, 8, 4)
# If more than 1199 entities are requested at once, the ndb query.fetch_page()
# operation will stall.
MAX_ENTITIES_PER_REQUEST = 1199


def _BigFetch(query, page_size=MAX_ENTITIES_PER_REQUEST):
  print 'Please wait. Fetching results at a rate of ~400 records per second...'
  cursor = None
  is_more = True
  big_results = []

  while is_more:
    results, cursor, is_more = query.fetch_page(page_size, start_cursor=cursor)
    big_results.extend(results)

  print 'Finished fetching results.'
  return big_results


def _FetchAnalyses(start_date, end_date):
  analyses_query = WfAnalysis.query(
      WfAnalysis.build_start_time >= start_date,
      WfAnalysis.build_start_time < end_date)

  return _BigFetch(analyses_query)


def _GetBuildId(base_build_model):
  """Get 'master_name/builder_name/build_number' key for base_build_model."""
  return base_build_model.key.pairs()[0][1]


def _FetchBuildsFromAnalyses(analyses):
  """Fetch builds that have the same keys as analyses.

  Args:
    analyses: A list of WfAnalyses objects for which to get builds.

  Returns:
    A dict of builds in {build_id: build} format. Example:
    {'m/b/1': build_1, 'm/b/2': build_2}
  """
  build_keys = []
  for analysis in analyses:
    build_keys.append(WfBuild._CreateKey(
        analysis.master_name, analysis.builder_name, analysis.build_number))

  builds = ndb.get_multi(build_keys)

  return {_GetBuildId(build): build for build in builds}


def _GetPickleFilePath():
  findit_tmp_dir = os.environ.get('TMP_DIR', os.getcwd())
  return os.path.join(findit_tmp_dir, 'analyses.pickle')


def _SaveAnalyses(analyses):
  pickled_analyses = pickle.dumps(analyses)
  with open(_GetPickleFilePath(), 'w') as f:
    f.write(pickled_analyses)


def _LoadAnalyses():
  with open(_GetPickleFilePath(), 'r') as f:
    pickled_analyses = f.read()
  print 'Loading pickled analyses...'
  analyses = pickle.loads(pickled_analyses)
  print 'Loaded pickled analyses.\n'
  return analyses


def _GetSuspectedRevisionsFromAnalysis(analysis):
  if analysis.suspected_cls:
    return [cl['revision'] for cl in analysis.suspected_cls if 'revision' in cl]
  return []


def _GroupCompileFailureAnalyses(analyses):
  groups = defaultdict(list)
  for analysis in analyses:
    revisions = _GetSuspectedRevisionsFromAnalysis(analysis)
    if revisions:
      groups[tuple(revisions)].append(analysis)

  # Copy defaultdict group values into list. Only include groups that have two
  # or more analyses.
  return [group for group in groups.itervalues() if len(group) > 1]


def _GetSecondsBetweenTwoTimesInGroup(group, first, second):
  seconds_difference = group[second] - group[first]
  return int(round(seconds_difference))


def _GetSecondsBetweenTwoTimesInGroupList(groups, first, second):
  return [_GetSecondsBetweenTwoTimesInGroup(group, first, second)
          for group in groups]


def _GetBuildEndTimeForAnalysis(analysis, builds):
  """Extracts the build end time from a WfBuild object.

  Args:
    analysis: The analysis with the same key as the WfBuild object.
    builds: A dict containing all the WfBuilds objects.

  Returns:
    The time the build ended in UNIX-like seconds (float).
  """
  key = _GetBuildId(analysis)
  build_data = builds[key].data
  build_end_time = json.loads(build_data)['times'][1]
  return build_end_time


def _GetTimesGroupFromAnalysesGroup(analyses_group, builds):
  return [_GetBuildEndTimeForAnalysis(analysis, builds)
          for analysis in analyses_group]


def _GetSecondsBetweenAllTimesInGroupList(groups):
  """Returns the number of seconds between all time stamps in a list of groups.

  Args:
    groups: A list of lists of timestamps. Example: [[4,5,6], [5,10]]

  Returns:
    A list of lists of differences of timestamps. Example [[1,1], [5]]
  """
  return [list(numpy.diff(group)) for group in groups]


def GetAndShowResults():
  # Set up the Remote API to use services on the live App Engine.
  remote_api.EnableRemoteApi(app_id='findit-for-me')

  # Try to load analyses from cache file on disk. If analyses can't be loaded
  # from disk, retrieve analyses from remote API, and save to disk.

  try:
    all_analyses = _LoadAnalyses()
  except IOError:
    all_analyses = _FetchAnalyses(START_DATE, END_DATE)
    _SaveAnalyses(all_analyses)

  compile_analyses = [analysis for analysis in all_analyses
                      if analysis.failure_type == failure_type.COMPILE
                      and analysis.correct]

  builds = _FetchBuildsFromAnalyses(compile_analyses)

  compile_analyses_groups = _GroupCompileFailureAnalyses(compile_analyses)
  print 'Number of compile_analyses_groups: %d' % len(compile_analyses_groups)

  time_groups = [sorted(_GetTimesGroupFromAnalysesGroup(group, builds))
                 for group in compile_analyses_groups]
  group_sizes = [len(group) for group in time_groups]
  average_analyses = numpy.average(group_sizes)
  median_analyses = numpy.median(group_sizes)
  standard_deviation_analyses = numpy.std(group_sizes)
  average_seconds_between_first_two_analyses_list = (
      numpy.average(_GetSecondsBetweenTwoTimesInGroupList(time_groups, 0, 1)))
  average_seconds_between_first_and_last_analyses_list = (
      numpy.average(_GetSecondsBetweenTwoTimesInGroupList(time_groups, 0, -1)))
  seconds_between_all_times = _GetSecondsBetweenAllTimesInGroupList(time_groups)
  average_of_average_seconds_between_all_times = numpy.average(
      [numpy.average(durations) for durations in seconds_between_all_times])
  builders = Counter([analyses_group[0].builder_name
                      for analyses_group in compile_analyses_groups])

  print ('Average (mean) number of analyses in each group: %d' %
         average_analyses)
  print ('Median number of analyses in each group: %d' %
         median_analyses)
  print ('Standard deviation of number of analyses in each group: %d' %
         standard_deviation_analyses)
  print
  print ('Average seconds between first two analyses\' request times: %d '
         'seconds' % average_seconds_between_first_two_analyses_list)
  print ('Average seconds between first and last analyses\' request times: %d '
         'seconds' % average_seconds_between_first_and_last_analyses_list)
  print ('Average of average seconds between all analyses\' request times: %d '
         'seconds' % average_of_average_seconds_between_all_times)
  print
  print 'Builders of first analyses in each group:'
  print builders

if __name__ == '__main__':
  GetAndShowResults()
