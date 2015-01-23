# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from itertools import chain
import logging

import webapp2

from model.record import Record
from shared.config import (
  TAG_START,
  TAG_STOP,
  TAG_ISSUE,
  TAG_PATCHSET,
  TRYJOBVERIFIER,
  JOB_STATE,
  RIETVELD_TIMESTAMP_FORMAT,
)
from shared.utils import (
  cross_origin_json,
  to_unix_timestamp,
)


class PatchSummary(webapp2.RequestHandler): # pragma: no cover
  @cross_origin_json
  def get(self, issue, patch): # pylint: disable=W0221
    now = to_unix_timestamp(datetime.utcnow())
    return summarize_patch(issue, patch, now)


def summarize_patch(issue, patch, now): # pragma: no cover
  attempts = [
    summarize_attempt(raw_attempt, now)
    for raw_attempt in get_raw_attempts(issue, patch)][::-1]
  return {
    'success': any(attempt['success'] for attempt in attempts),
    'begin': maybe_min(attempt['begin'] for attempt in attempts),
    'end': maybe_max(attempt['end'] for attempt in attempts),
    'durations': {
      field: sum(attempt['durations'][field] for attempt in attempts)
      for field in blank_durations_summary()
    },
    'job_counts': {
      state: sum(len(attempt['jobs'][state]) for attempt in attempts)
      for state in JOB_STATE.itervalues()
    },
    'flaky_jobs': get_flaky_jobs(attempts),
    'attempt_count': len(attempts),
    'attempt_fail_count': sum(
        1
        for attempt in attempts
        if attempt['success'] == False),
    'attempts': attempts,
  }


def get_raw_attempts(issue, patch): # pragma: no cover
  query = Record.query().order(Record.timestamp).filter(
    Record.tags == TAG_ISSUE % issue,
    Record.tags == TAG_PATCHSET % patch)
  raw_attempts = []
  raw_attempt = None
  for record in query:
    if raw_attempt == None and TAG_START in record.tags:
      raw_attempt = []
    if raw_attempt != None:
      raw_attempt.append(record)
      if TAG_STOP in record.tags:
        raw_attempts.append(raw_attempt)
        raw_attempt = None
  if raw_attempt != None and len(raw_attempt) > 0:
    raw_attempts.append(raw_attempt)
  return raw_attempts


def summarize_attempt(raw_attempt, now): # pragma: no cover
  assert len(raw_attempt) > 0
  start_timestamp = to_unix_timestamp(raw_attempt[0].timestamp)
  summary = blank_attempt_summary()
  job_tracker = AttemptJobTracker(start_timestamp)
  durations = summary['durations']
  last_patch_action = None
  last_patch_timestamp = None
  verifier_start_timestamp = None
  for record in raw_attempt:
    action = record.fields.get('action')
    # patch_ready_to_commit signals are noisy and not useful.
    if action == 'patch_ready_to_commit':
      continue
    verifier = record.fields.get('verifier')
    timestamp = to_unix_timestamp(record.timestamp)
    if last_patch_action:
      patch_state_duration = timestamp - last_patch_timestamp

    # Verifier job updates.
    if verifier == TRYJOBVERIFIER:
      if action == 'verifier_start':
        verifier_start_timestamp = timestamp
      elif action == 'verifier_jobs_update':
        job_tracker.update_jobs(record)
      elif action in ('verifier_pass', 'verifier_fail'):
        durations['running_all_jobs'] = timestamp - verifier_start_timestamp
        verifier_start_timestamp = None

    # Patch state updates.
    if action and action.startswith('patch_'):
      if last_patch_action == 'patch_throttled':
        durations['blocked_on_throttled_tree'] += patch_state_duration
      if last_patch_action == 'patch_tree_closed':
        durations['blocked_on_closed_tree'] += patch_state_duration
    if action == 'patch_committed':
      summary['success'] = True
      if last_patch_action == 'patch_committing':
        durations['committing'] += patch_state_duration
    if action == 'patch_failed':
      summary['success'] = False
      summary['fail_reason'] = record.fields.get('reason')
    if action == 'patch_stop':
      summary['end'] = timestamp
    if action and action.startswith('patch_'):
      last_patch_action = action
      last_patch_timestamp = timestamp

  # Finalize attempt durations.
  summary['begin'] = start_timestamp
  if summary['end'] != None:
    durations['total'] = summary['end'] - summary['begin']
  last_timestamp = summary['end'] or now
  if last_patch_action:
    patch_state_duration = last_timestamp - last_patch_timestamp
  if last_patch_action == 'patch_tree_closed':
    durations['blocked_on_closed_tree'] += patch_state_duration
  if last_patch_action == 'patch_throttled':
    durations['blocked_on_throttled_tree'] += patch_state_duration
  if last_patch_action == 'patch_committing':
    durations['committing'] += patch_state_duration
  if verifier_start_timestamp:
    durations['running_all_jobs'] = last_timestamp - verifier_start_timestamp

  # Finalize jobs and job durations.
  summary['jobs'] = job_tracker.summarize_jobs(
      summary['success'] != None, last_timestamp)

  return summary


class AttemptJobTracker(object): # pragma: no cover
  def __init__(self, cutoff_timestamp):
    self.cutoff_timestamp = cutoff_timestamp
    self.jobs = {}

  def update_jobs(self, record):
    job_states = record.fields.get('jobs', {})
    for cq_job_state, jobs in job_states.iteritems():
      job_state = JOB_STATE.get(cq_job_state)
      if not job_state:
        logging.warning('Unknown job state: %s', cq_job_state)
        continue
      for job_info in jobs:
        master = job_info.get('master')
        builder = job_info.get('builder')
        self.jobs.setdefault(master, {})
        self.jobs[master].setdefault(builder, {})
        job_info = job_info or {}
        timestamp = self.rietveld_timestamp(job_info.get('timestamp'))
        # Ignore jobs from past attempts.
        if not timestamp or timestamp < self.cutoff_timestamp:
          continue
        build_number = job_info.get('buildnumber')
        if not build_number:
          logging.warning('No build number for %s %s at %s.' % (
              master, builder, timestamp))
          continue
        job = self.jobs[master][builder].setdefault(build_number, {})
        if len(job) == 0:
          job.update(blank_job_summary())
          job.update({
            'begin': timestamp,
            'master': master,
            'builder': builder,
            'slave': job_info.get('slave'),
            'build_number': build_number,
          })
        if job_state != 'running':
          job['end'] = timestamp
          job['duration'] = timestamp - job['begin']
        job['state'] = job_state
        job['retry'] = any(
            same_builder(job, test_job) and
            job['build_number'] != test_job['build_number'] and
            test_job['begin'] < job['begin']
            for test_job in self.jobs[master][builder].itervalues())
        # The build URL is sometimes missing so ensure we set it
        # if it was not already set.
        job['url'] = job['url'] or job_info.get('url')

  @staticmethod
  def rietveld_timestamp(timestamp_string):
    try:
      return to_unix_timestamp(
          datetime.strptime(timestamp_string, RIETVELD_TIMESTAMP_FORMAT))
    except ValueError:
      logging.warning('Failed to parse Rietveld timestamp: ' + timestamp_string)
      return None

  def summarize_jobs(self, attempt_ended, last_timestamp):
    summaries = {state: [] for state in JOB_STATE.itervalues()}
    for builds in self.jobs.itervalues():
      for jobs in builds.itervalues():
        for job in jobs.itervalues():
          if job['end'] == None:
            if attempt_ended:
              job['end'] = last_timestamp
            job['duration'] = last_timestamp - job['begin']
          summaries[job['state']].append(job)
    for jobs in summaries.itervalues():
      jobs.sort(cmp=lambda x, y: cmp(y['begin'], x['begin']))
    return summaries


def blank_attempt_summary(): # pragma: no cover
  return {
    'success': None,
    'fail_reason': None,
    'begin': None,
    'end': None,
    'durations': blank_durations_summary(),
    'jobs': {state: [] for state in JOB_STATE.itervalues()},
  }


def blank_durations_summary(): # pragma: no cover
  return {
    'running_all_jobs': 0,
    'blocked_on_closed_tree': 0,
    'blocked_on_throttled_tree': 0,
    'committing': 0,
    'total': 0,
  }


def blank_job_summary(): # pragma: no cover
  return {
    'state': None,
    'retry': False,
    'begin': None,
    'end': None,
    'duration': 0,
    'master': None,
    'builder': None,
    'slave': None,
    'build_number': None,
    'url': None,
  }


def get_flaky_jobs(attempts): # pragma: no cover
  flaky_jobs = []
  passed_jobs = set()
  for attempt in attempts:
    for job in attempt['jobs']['passed']:
      passed_jobs.add(job_builder_id(job))
  for attempt in attempts:
    for job in attempt['jobs']['failed']:
      if job_builder_id(job) in passed_jobs:
        flaky_jobs.append(job)
  return flaky_jobs


def job_builder_id(job): # pragma: no cover
  return (job['master'], job['builder'])


def same_builder(job_a, job_b): # pragma: no cover
  return job_builder_id(job_a) == job_builder_id(job_b)


def maybe_min(iterable): # pragma: no cover
  try:
    return min(iterable)
  except ValueError:
    return None


def maybe_max(iterable): # pragma: no cover
  try:
    return max(iterable)
  except ValueError:
    return None
