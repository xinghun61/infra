# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import dateutil.parser
import logging
import json
import time
import urllib2

from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
from handlers.flake_issues import MIN_REQUIRED_FLAKY_RUNS
from infra_libs import ts_mon
from model.build_run import BuildRun
from model.build_run import PatchsetBuilderRuns
from model.fetch_status import FetchStatus
from model.flake import Flake
from model.flake import FlakeOccurrence
from model.flake import FlakyRun
from status import build_result, util
import time_functions.timestamp


requests_metric = ts_mon.CounterMetric(
    'flakiness_pipeline/cq_status/requests',
    description='Requests made to the chromium-cq-status API')
flakes_metric = ts_mon.CounterMetric(
    'flakiness_pipeline/flake_occurrences_detected',
    description='Detected flake occurrences')


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


# Updates a Flake object, which spans all the instances of one flake, with the
# time of an occurrence of that flake.
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
    util.add_occurrence_time_to_flake(flake, o.failure_run_time_finished)
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
  # Only process flakes that happened at least MIN_REQUIRED_FLAKY_RUNS times in
  # the last 24 hours.
  for flake in Flake.query(Flake.count_day >= MIN_REQUIRED_FLAKY_RUNS,
                           projection=[Flake.count_day]):
    taskqueue.add(queue_name='issue-updates',
                  url='/issues/process/%s' % flake.key.urlsafe())


def update_stale_issues():
  for flake in Flake.query(Flake.issue_id > 0, projection=[Flake.issue_id],
                           distinct=True):
    taskqueue.add(queue_name='issue-updates',
                  url='/issues/update-if-stale/%s' % flake.issue_id)


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
          timestamp_tz = dateutil.parser.parse(job['timestamp'])
          # We assume timestamps from chromium-cq-status are already in UTC.
          timestamp = timestamp_tz.replace(tzinfo=None)
        except KeyError:
          continue

        try:
          buildnumber = get_int_value(build_properties, 'buildnumber')
          issue = get_int_value(build_properties, 'issue')
          patchset = get_int_value(build_properties, 'patchset')
          attempt_start_ts = get_int_value(build_properties, 'attempt_start_ts')
          time_started = datetime.datetime.utcfromtimestamp(
              attempt_start_ts / 1000000)
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
                             time_started=time_started,
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
            failure_run = previous_run
            success_run = build_run
          else:
            # We saw the pass and then the failure. Could happen when fetching
            # historical data, or for the bot_update step (patch can't be
            # applied cleanly anymore).
            failure_run = build_run
            success_run = previous_run

          logging_output.append(failure_run.key.parent().get().builder +
                                str(failure_run.buildnumber))

          # Queue a task to fetch the error of this failure and create FlakyRun.
          flakes_metric.increment_by(1)
          taskqueue.add(
              queue_name='issue-updates',
              url='/issues/create_flaky_run',
              params={'failure_run_key': failure_run.key.urlsafe(),
                      'success_run_key': success_run.key.urlsafe()})

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
        requests_metric.increment_by(1, fields={'status': 'parse_error'})
        logging.exception('failed to parse CQ data from %s', url)
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
      else:
        requests_metric.increment_by(1, fields={'status': 'success'})

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
      requests_metric.increment_by(1, fields={'status': 'fetch_error'})
      logging.warning('Failed to fetch CQ status: %s', e.reason)
