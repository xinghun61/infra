# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os
import pickle
import Queue
import re
import sys
import time
from threading import Thread

_APPENGINE_SDK_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
    os.path.pardir, os.path.pardir, 'google_appengine')
sys.path.insert(1, _APPENGINE_SDK_DIR)
from google.appengine.ext import ndb

_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(1, _FINDIT_DIR)
from local_libs import remote_api

from common.findit_http_client import FinditHttpClient
from libs import time_util
from model.wf_analysis import WfAnalysis
from pipeline_utils.appengine_third_party_pipeline_python_src_pipeline \
    import pipeline

_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
sys.path.insert(0, _THIRD_PARTY_DIR)
import google
google.__path__.insert(0, os.path.join(_THIRD_PARTY_DIR, 'google'))

from handlers import handlers_util
from waterfall import swarming_util

NOW = time_util.GetUTCNow()
START_DATE, END_DATE = datetime.datetime(2017, 1, 1), NOW
THREAD_COUNT = 64

# If more than 1199 entities are requested at once, the ndb query.fetch_page()
# operation will stall.
MAX_ENTITIES_PER_REQUEST = 1199
CLIENT_SINGLETON = FinditHttpClient()


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
  analyses_query = WfAnalysis.query(WfAnalysis.build_start_time >= start_date,
                                    WfAnalysis.build_start_time < end_date)

  return _BigFetch(analyses_query)


def _GetPickleFilePath():
  findit_tmp_dir = os.environ.get('TMP_DIR', os.getcwd())
  return (os.path.join(findit_tmp_dir, 'analyses.pickle'), os.path.join(
      findit_tmp_dir, 'records.pickle'))


def _SaveAnalyses(analyses, records):
  pickled_analyses = pickle.dumps(analyses)
  pickled_records = pickle.dumps(records)
  analyses_path, records_path = _GetPickleFilePath()
  with open(analyses_path, 'w') as f:
    f.write(pickled_analyses)
  with open(records_path, 'w') as f:
    f.write(pickled_records)


def _LoadAnalyses():
  analyses_path, records_path = _GetPickleFilePath()
  with open(analyses_path, 'r') as f:
    pickled_analyses = f.read()
  with open(records_path, 'r') as f:
    pickled_records = f.read()
  print 'Loading pickled analyses...'
  analyses = pickle.loads(pickled_analyses)
  times = [
      x.build_start_time for x in analyses if hasattr(x, 'build_start_time')
  ]
  records = pickle.loads(pickled_records)
  return analyses, min(times), max(times), records


def _GetTimesFromPipeline(pid):
  result = {}
  suffixes = {}
  status_tree = pipeline.get_status_tree(pid)
  for _, child_status in status_tree.get('pipelines', {}).iteritems():
    cls = child_status['classPath'].split('.')[-1]
    start = child_status.get('startTimeMs')
    end = child_status.get('endTimeMs')
    if start and end:
      if (cls + '.start' + suffixes.get(cls, '')) in result.keys():
        old_suffix = suffixes.get(cls, '.0')
        old_index = int(old_suffix[1:])
        suffixes[cls] = '.' + str(old_index + 1)
      result['pl.' + cls + '.start' + suffixes.get(cls, '')] = (
          _UnknownToDatetime(start))
      result['pl.'
             + cls + '.end' + suffixes.get(cls, '')] = (_UnknownToDatetime(end))
  return result


def _GetTimes(q, r):
  """Obtains times of interest from a WfAnalysis instance.

  This is meant to be run by a worker thread."""
  while True:
    a = q.get()
    result = {
        'wfa.build_start_time': a.build_start_time,
        'wfa.request_time': a.request_time,
        'wfa.start_time': a.start_time,
        'wfa.end_time': a.end_time,
        'wfa.updated_time': a.updated_time,
        'wfa.result_status': a.result_status,
        'wfa.build_failure_type': a.build_failure_type,
    }
    try:
      tryjobs_times = {}
      step_to_tryjobs = handlers_util.GetAllTryJobResults(
          a.master_name, a.builder_name, a.build_number, True)
      for step in step_to_tryjobs.keys():
        this_tryjobs = step_to_tryjobs[step]['try_jobs']
        for job in this_tryjobs:
          if job.get('try_job_url'):
            tryjobs_times.setdefault('try.' + step, {})
            times = _GetTimesFromBuildbot(job['try_job_url'])
            tryjobs_times['try.' + step].update(times)
          if job.get('task_url'):
            tryjobs_times.setdefault('swarm.' + step, {})
            times = _GetTimesFromSwarming(job['task_url'])
            tryjobs_times['swarm.' + step].update(times)

      result.update(tryjobs_times)
      if a.pipeline_status_path:
        pipeline_root = re.search(r'(?<=root\=)[^&]*',
                                  a.pipeline_status_path).group(0)
        result.update(_GetTimesFromPipeline(pipeline_root))
      r.put((a.key, result))
    except Exception, e:
      print 'Problem with ', a.key, e

    q.task_done()


def _GetTimesFromBuildbot(buildbot_url):
  # TODO(robertocn): Use existing code that talks to milo.
  # Convert the buildbot url to request to milo.
  milo_url = ('https://luci-milo.appspot.com/prpc/'
              'milo.Buildbot/GetBuildbotBuildJSON')
  # http://build.chromium.org/p/<master>/builders/<builder>/builds/<number>
  master, _, builder, _, buildnum = str(buildbot_url).split('/')[4:]
  data = json.dumps({
      'master': master,
      'builder': builder,
      'buildNum': buildnum,
      'exclude_deprecated': True,
  })

  _, response = CLIENT_SINGLETON.Post(
      milo_url, data, headers={'Content-Type': 'application/json'})

  response_json = response[response.index('{'):]
  response_data = json.loads(response_json)
  result = {}
  for step in response_data['steps']:
    if 'name' in step and 'times' in step:
      # Times from buildbot seem to be in PST, naively converting to UTC
      start = _UnknownToDatetime(step['times'][0])
      end = _UnknownToDatetime(step['times'][1])
      if start:
        result[step['name'] + '.start'] = start + datetime.timedelta(hours=8)
      if end:
        result[step['name'] + '.end'] = end + datetime.timedelta(hours=8)
  return result


def _GetTimesFromSwarming(url):
  results = {}
  task_id = url.split('/')[-1]
  task_result, _ = swarming_util.GetSwarmingTaskResultById(
      task_id, CLIENT_SINGLETON)
  for k in task_result.keys():
    if k.endswith('_ts'):
      results[k] = _UnknownToDatetime(task_result[k])
  return results


# TODO: Instead of guessing, make the right conversions when retrieving data,
# including timezone adjustment (i.e. make everything UTC)
def _UnknownToDatetime(unknown):
  if isinstance(unknown, datetime.datetime):
    return unknown
  if isinstance(unknown, int) and unknown < 1000000000:  # Timestamp in 2001
    return unknown
  if isinstance(unknown, basestring):
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
      try:
        return datetime.datetime.strptime(unknown, fmt)
      except ValueError:
        pass
  # This is only used to guess whether the time given is in seconds or ms
  epoch = time.mktime(datetime.datetime(year=2008, month=9, day=2).timetuple())
  try:
    ts = float(unknown)
    if ts > epoch:
      if ts > epoch * 1000:
        ts = float(ts) / 1000
    return datetime.datetime.fromtimestamp(ts)
  except (TypeError, ValueError):
    # Couldn't cast it, return the original value.
    pass
  return unknown


def _PrependKeys(prefix, d):
  new_d = {}
  for k in d.keys():
    new_d[prefix + k] = d[k]
  return new_d


def _Denest(d):
  """Converts {'a': {'b': 'c'}} into {'a.b': 'c'}."""
  if isinstance(d, dict):
    removals = []
    insertions = {}
    for k, v in d.iteritems():
      if isinstance(v, dict):
        insertions.update(_PrependKeys(k + '.', v))
        removals.append(k)
    for k in removals:
      del (d[k])
    d.update(insertions)
  return d


def main():
  # TODO: add options to limit the date range to fetch
  # TODO: add options to display summary of fetched info.

  remote_api.EnableRemoteApi(app_id='findit-for-me')

  try:
    all_analyses, stored_start, stored_end, time_records = _LoadAnalyses()
  except IOError:
    all_analyses = _FetchAnalyses(START_DATE, END_DATE)
    time_records = {}
    _SaveAnalyses(all_analyses, time_records)
  else:
    if stored_start > START_DATE:
      all_analyses = _FetchAnalyses(START_DATE, stored_start) + all_analyses
    if END_DATE > stored_end:
      all_analyses += _FetchAnalyses(stored_end, END_DATE)
    _SaveAnalyses(all_analyses, time_records)
  saved_count = len(time_records)

  q = Queue.Queue()
  r = Queue.Queue()

  for _ in range(THREAD_COUNT):
    t = Thread(target=_GetTimes, args=(q, r))
    t.daemon = True
    t.start()

  for a in all_analyses:
    if a.key not in time_records.keys():
      q.put(a)

  while not (q.empty() and r.empty()):
    key, record = r.get()
    time_records[key] = _Denest(record)
    print len(time_records)
    if saved_count + THREAD_COUNT < len(time_records):
      _SaveAnalyses(all_analyses, time_records)
      saved_count = len(time_records)
      print 'Saved %d results' % saved_count
  q.join()


if __name__ == '__main__':
  main()
