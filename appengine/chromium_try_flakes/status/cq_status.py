# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import json
import time
import urllib2

from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
from model.build_run import BuildRun
from model.build_run import PatchsetBuilderRuns
from model.fetch_status import FetchStatus
from model.flake import Flake
from model.flake import FlakeOccurance
from model.flake import FlakyRun
from status import build_result
import time_functions.timestamp


@ndb.transactional
def get_patchset_builder_runs(issue, patchset, master, builder):
  patchset_builder_runs_id = PatchsetBuilderRuns.getId(issue, patchset, master,
                                                       builder)

  patchset_builder_runs = PatchsetBuilderRuns.get_by_id(
      patchset_builder_runs_id)
  if not patchset_builder_runs:
    patchset_builder_runs = PatchsetBuilderRuns(issue=issue,
                                                patchset=patchset,
                                                master=master,
                                                builder=builder,
                                                id=patchset_builder_runs_id)
    patchset_builder_runs.put()

  return patchset_builder_runs


def is_last_hour(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(hours=1)


def is_last_day(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(days=1)


def is_last_week(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(weeks=1)


def is_last_month(date):
  return (datetime.datetime.utcnow() - date) < datetime.timedelta(days=31)


# Updates a Flake object, which spans all the instances of one flake, with the
# time of an occurance of that flake.
def add_occurance_time_to_flake(flake, occurance_time):  # pragma: no cover
  if occurance_time > flake.last_time_seen:
    flake.last_time_seen = occurance_time
  if is_last_hour(occurance_time):
    flake.count_hour += 1
    flake.last_hour = True
  if is_last_day(occurance_time):
    flake.count_day += 1
    flake.last_day = True
  if is_last_week(occurance_time):
    flake.count_week += 1
    flake.last_week = True
  if is_last_month(occurance_time):
    flake.count_month += 1
    flake.last_month = True
  flake.count_all += 1


# Calculate the counters for a Flake object.
def update_flake_counters(flake):  # pragma: no cover
  occurrences = ndb.get_multi(flake.occurrences)
  flake.count_hour = 0
  flake.count_day = 0
  flake.count_week = 0
  flake.count_month = 0
  flake.count_all = 0
  flake.last_hour = False
  flake.last_day = False
  flake.last_week = False
  flake.last_month = False
  flake.last_time_seen = datetime.datetime.min
  for o in occurrences:
    add_occurance_time_to_flake(flake, o.failure_run_time_finished)
  flake.put()


# The following four functions are cron jobs which update the counters for
# flakes. To speed things up, we don't update last month/week/day as often as we
# update hourly counters.
def update_flake_hour_counter():  # pragma: no cover
  query = Flake.query().filter(Flake.last_hour == True)
  for flake in query:
    update_flake_counters(flake)


def update_flake_day_counter():  # pragma: no cover
  query = Flake.query().filter(Flake.last_day == True,
                               Flake.last_hour == False)
  for flake in query:
    update_flake_counters(flake)


def update_flake_week_counter():  # pragma: no cover
  query = Flake.query().filter(Flake.last_week == True,
                               Flake.last_day == False,
                               Flake.last_hour == False)
  for flake in query:
    update_flake_counters(flake)


def update_flake_month_counter():  # pragma: no cover
  query = Flake.query().filter(Flake.last_month == True,
                               Flake.last_week == False,
                               Flake.last_day == False,
                               Flake.last_hour == False)
  for flake in query:
    update_flake_counters(flake)


def update_issue_tracker():
  """File/update issues for flakes on issue_tracker."""
  # Only process flakes that happened at least 10 times in the last 24 hours.
  for flake in Flake.query(Flake.count_day >= 10, projection=[Flake.count_day]):
    taskqueue.add(queue_name='issue-updates',
                  url='/issues/process/%s' % flake.key.urlsafe())


@ndb.transactional(xg=True)  # pylint: disable=no-value-for-parameter
def add_failure_to_flake(name, flaky_run):
  flake = Flake.get_by_id(name)
  if not flake:
    flake = Flake(name=name, id=name, last_time_seen=datetime.datetime.min)
    flake.put()

  flake.occurrences.append(flaky_run.key)

  flaky_run_time = flaky_run.failure_run.get().time_finished
  add_occurance_time_to_flake(flake, flaky_run_time)

  flake.put()

# see examples:
# compile http://build.chromium.org/p/tryserver.chromium.mac/json/builders/
#         mac_chromium_compile_dbg/builds/11167?as_text=1
# gtest http://build.chromium.org/p/tryserver.chromium.win/json/builders/
#       win_chromium_x64_rel_swarming/builds/4357?as_text=1
# TODO(jam): get specific problem with compile so we can use that as name
# TODO(jam): It's unfortunate to have to parse this html. Can we get it from
# another place instead of the tryserver's json?
def get_flakes(step):
  combined = ' '.join(step['text'])

  # If test results were invalid, report whole step as flaky.
  if 'TEST RESULTS WERE INVALID' in combined:
    return [combined]

  #gtest
  gtest_search_str = 'failures:<br/>'
  gtest_search_index = combined.find(gtest_search_str)
  if gtest_search_index != -1:
    failures = combined[gtest_search_index + len(gtest_search_str):]
    failures = failures.split('<br/>')
    results = []
    for failure in failures:
      if not failure:
        continue
      if failure == 'ignored:':
        break  # layout test output
      results.append(failure)
    return results

  #gpu
  gpu_search_str = '&tests='
  gpu_search_index = combined.find(gpu_search_str)
  if gpu_search_index != -1:
    failures = combined[gpu_search_index + len(gpu_search_str):]
    end_index = failures.find('">')
    failures = failures[:end_index  ]
    failures = failures.split(',')
    results = []
    for failure in failures:
      if not failure:
        continue
      results.append(failure)
    return results

  return [combined]


# A queued task which polls the tryserver to get more information about why a
# run failed.
def get_flaky_run_reason(flaky_run_key):
  flaky_run = flaky_run_key.get()
  failure_run = flaky_run.failure_run.get()
  patchset_builder_runs = failure_run.key.parent().get()
  url = ('http://build.chromium.org/p/' + patchset_builder_runs.master +
         '/json/builders/' + patchset_builder_runs.builder +'/builds/' +
         str(failure_run.buildnumber))
  urlfetch.set_default_fetch_deadline(60)
  logging.info('get_flaky_run_reason ' + url)
  result = urlfetch.fetch(url).content
  try:
    json_result = json.loads(result)
  except ValueError:
    logging.error('couldnt decode json for ' + url)
    return
  steps = json_result['steps']

  failed_steps = []
  passed_steps = []
  for step in steps:
    result = step['results'][0]
    if build_result.isResultSuccess(result):
      passed_steps.append(step)
      continue
    if not build_result.isResultFailure(result):
      continue
    step_name = step['name']
    if step_name == 'steps' or step_name.startswith('[swarming]') or \
       step_name == 'presubmit':
      # recipe code shows errors twice with first being 'steps'. also when a
      # swarming test fails, it shows up twice. also ignore 'presubmit' since
      # it changes from fail to pass for same patchset depending on new lgtm.
      continue
    failed_steps.append(step)

  steps_to_ignore = []
  for step in failed_steps:
    step_name = step['name']
    if ' (with patch)' in step_name:
      # Android instrumentation tests add a prefix before the step name, which
      # doesn't appear on the summary step (without suffixes). To make sure we
      # correctly ignore duplicate failures, we remove the prefix.
      step_name = step_name.replace('Instrumentation test ', '')

      step_name_with_no_modifier = step_name.replace(' (with patch)', '')
      for other_step in failed_steps:
        # A step which fails, and then is retried and also fails, will have its
        # name without the ' (with patch)' again. Don't double count.
        if other_step['name'] == step_name_with_no_modifier:
          steps_to_ignore.append(other_step['name'])

      # If a step fails without the patch, then the tree is busted. Don't count
      # as flake.
      step_name_without_patch = step_name_with_no_modifier + ' (without patch)'
      for other_step in failed_steps:
        if other_step['name'] == step_name_without_patch:
          steps_to_ignore.append(step['name'])
          steps_to_ignore.append(other_step['name'])

  for step in failed_steps:
    step_name = step['name']
    if step_name in steps_to_ignore:
      continue
    flakes = get_flakes(step)
    if not flakes:
      continue
    for flake in flakes:
      flake_occurance = FlakeOccurance(name=step_name, failure=flake)
      flaky_run.flakes.append(flake_occurance)

      add_failure_to_flake(flake, flaky_run)
  flaky_run.put()


def get_int_value(properties, key):
  if not key in properties:
    raise ValueError('key not found')
  value = properties[key]
  if type(value) == type(list()):
    value = value[0]
  return int(value)


# Parses the json which we get from chromium-cq-status.
def parse_cq_data(json_data):
  logging_output = []
  for result in json_data.get('results', {}):
    fields = result.get('fields', [])
    if not 'action' in fields:
      continue

    action = fields.get('action')
    if action != 'verifier_jobs_update':
      continue

    if fields.get('verifier') != 'try job':
      continue

    # At the moment, much of the parsing logic assumes this is a Chromium
    # tryjob.
    if fields.get('project') != 'chromium':
      continue

    job_states = fields.get('jobs', [])
    for state in job_states:
      # Just go by |result|.
      #if state not in ['JOB_SUCCEEDED', 'JOB_FAILED', 'JOB_TIMED_OUT']:
      #  continue

      for job in job_states[state]:
        build_properties = job.get('build_properties')
        if not build_properties:
          continue

        try:
          master = job['master']
          builder = job['builder']
          result = job['result']
          timestamp = datetime.datetime.strptime(job['timestamp'],
                                                 '%Y-%m-%d %H:%M:%S.%f')
        except KeyError:
          continue

        try:
          buildnumber = get_int_value(build_properties, 'buildnumber')
          issue = get_int_value(build_properties, 'issue')
          patchset = get_int_value(build_properties, 'patchset')
        except ValueError:
          continue

        if build_result.isResultPending(result):
          continue

        # At this point, only success or failure.
        success = build_result.isResultSuccess(result)

        patchset_builder_runs = get_patchset_builder_runs(issue=issue,
                                                          patchset=patchset,
                                                          master=master,
                                                          builder=builder)

        build_run = BuildRun(parent=patchset_builder_runs.key,
                             buildnumber=buildnumber,
                             result=result,
                             time_finished=timestamp)

        previous_runs = BuildRun.query(
            ancestor=patchset_builder_runs.key).fetch()

        duplicate = False
        for previous_run in previous_runs:
          # We saw this build run already or there are multiple green runs,
          # in which case we ignore subsequent ones to avoid showing failures
          # multiple times.
          if (previous_run.buildnumber == buildnumber) or \
             (build_run.is_success and previous_run.is_success) :
            duplicate = True
            break

        if duplicate:
          continue

        build_run.put()

        for previous_run in previous_runs:
          if previous_run.is_success == build_run.is_success:
            continue
          if success:
            # We saw the flake and then the pass.
            flaky_run = FlakyRun(
                failure_run=previous_run.key,
                failure_run_time_finished=previous_run.time_finished,
                success_run=build_run.key)
            flaky_run.put()
            logging_output.append(previous_run.key.parent().get().builder +
                                  str(previous_run.buildnumber))
          else:
            # We saw the pass and then the failure. Could happen when fetching
            # historical data.
            flaky_run = FlakyRun(
                failure_run=build_run.key,
                failure_run_time_finished=build_run.time_finished,
                success_run=previous_run.key)
            flaky_run.put()
            logging_output.append(build_run.key.parent().get().builder +
                                  str(build_run.buildnumber))

          # Queue a task to fetch the error of this failure.
          deferred.defer(get_flaky_run_reason, flaky_run.key)

  return logging_output


def fetch_cq_status():
  """Fetches data from chromium-cq-status app and saves new data.

  Remembers old cursor and fetches new data.
  """

  fetch_status = FetchStatus.query().get()
  cursor = ''
  begin = ''
  end = ''
  retry_count = 0

  while True:
    if fetch_status:
      if fetch_status.done:
        logging.info('historical fetching done so fetch latest...')
        end = str(time_functions.timestamp.utcnow_ts())

        last_build_run_seen = BuildRun.query().order(
            -BuildRun.time_finished).fetch(1)
        begin = str(time_functions.timestamp.utctimestamp(
            last_build_run_seen[0].time_finished))
        cursor = ''
      else:
        begin = fetch_status.begin
        end = fetch_status.end
        cursor = fetch_status.cursor
    else:
      logging.info('didnt find any historical information. fetching last week')
      begin = str(time_functions.timestamp.utctimestamp(
          datetime.datetime.utcnow() - datetime.timedelta(weeks=1)))
      end = str(time_functions.timestamp.utcnow_ts())

    if begin and end:
      logging.info('fetching from ' +
                   str(datetime.datetime.fromtimestamp(float(begin))) + ' to ' +
                   str(datetime.datetime.fromtimestamp(float(end))) +
                   ' cursor: ' + cursor)
    else:
      logging.info('fetching with no begin/end and cursor: ' + cursor)

    url = "https://chromium-cq-status.appspot.com/query"
    params = []
    params.append('tags=action=verifier_jobs_update')
    if cursor:
      params.append('cursor=' + cursor)
    if begin:
      params.append('begin=' + begin)
    if end:
      params.append('end=' + end)
    # Tried count of 200 or more but would get OOM or deadline errors. Even 50
    # sometimes gives:
    # "Values may not be more than 1000000 bytes in length; received 2118015
    # bytes"
    params.append('count=10')

    url += '?' + '&'.join(params)
    logging.info('fetching url: ' + url)

    try:
      urlfetch.set_default_fetch_deadline(60)
      result = urlfetch.fetch(url).content

      timestamp_str = '"timestamp":"'
      logging_idx = result.find(timestamp_str)
      if logging_idx != -1:
        logging_idx += len(timestamp_str)
        logging_idx2 = result.find('"', logging_idx)
        logging.info(' current fetch has time of ' +
                     result[logging_idx:logging_idx2])

      try:
        json_result = json.loads(result)

        more = json_result['more']
        cursor = json_result['cursor']

        try:
          logging_output = parse_cq_data(json_result)
          if logging_output:
            logging.info('found flakes: ' + ' '.join(logging_output))
        except DeadlineExceededError:
          logging.info('got DeadlineExceededError during parse_cq_data, '
                       'catching to not show up as error')
          return

      except ValueError:
        logging.info('couldnt decode json for ' + url)
        if 'DeadlineExceededError' in result:
          logging.error('got deadline exceeded, trying again after 1s')
          time.sleep(1)
          continue
        elif retry_count < 3:
          retry_count += 1
          logging.error('will retry after sleeping ' + str(retry_count))
          time.sleep(retry_count)
          continue
        else:
          logging.error('giving up and will count current fetch as done')
          # Don't want to continue this as could be a bad cursor.
          more = False

      if not fetch_status:
        fetch_status = FetchStatus()
      fetch_status.done = not more
      if fetch_status.done:
        fetch_status.cursor = ''
        fetch_status.begin = ''
        fetch_status.end = ''
        retry_count = 0
        logging.info('finished fetching for current cursor')
      else:
        fetch_status.begin = begin
        fetch_status.end = end
        fetch_status.cursor = cursor
      fetch_status.put()

      if not more:
        return  # finish the cron job and wait for next iteration
    except urllib2.URLError, e:
      logging.warning('Failed to fetch CQ status: %s', e.reason)
