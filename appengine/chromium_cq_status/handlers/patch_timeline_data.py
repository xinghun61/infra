# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides a JSON endpoint for CQ data as a series of Trace Viewer events.

From the CQ data posted to the datastore, patch_timeline will construct a JSON
object that can be parsed by Trace Viewer to create a timeline view.
"""

import copy
import json
import logging
import webapp2

from datetime import datetime
from model.record import Record
from shared.config import (
  JOB_STATE,
  RIETVELD_TIMESTAMP_FORMAT,
  TAG_ISSUE,
  TAG_PATCHSET,
)

from shared.utils import (
  cross_origin_json,
  to_unix_timestamp,
)

class PatchTimelineData(webapp2.RequestHandler): # pragma: no cover
  @cross_origin_json
  def get(self, issue, patch):
    attempts = get_attempts(issue, patch)
    return attempts_to_events(attempts)


def get_attempts(issue, patch): # pragma: no cover
  """Given an issue and a patch, returns a list of attempts.

  Returns a list of attempts. Attempts are lists of records which fall within
  the endpoints of patch_start and patch_stop actions, inclusive.
  """
  query = Record.query().order(Record.timestamp).filter(
    Record.tags == TAG_ISSUE % issue,
    Record.tags == TAG_PATCHSET % patch)
  attempt = None
  for record in query:
    action = record.fields.get('action')
    if attempt is None and action == 'patch_start':
      attempt = [record]
    # Sometimes CQ sends multiple patch_start in a single attempt. These
    # are ignored (only the first patch_start is kept).
    if attempt is not None and action != 'patch_start':
      attempt.append(record)
      if action == 'patch_stop':
        yield attempt
        attempt = None
  if attempt != None:
    yield attempt


def attempts_to_events(attempts): # pragma: no cover
  """Given a list of attempts, returns a list of Trace Viewer events.

  Attempts are a list of CQ records which fall between patch_start and
  patch_stop actions. Each record is converted to a Trace Viewer event
  of type 'B' or 'E', representing begin and end respectively.

  Occasinally CQ runs jobs without first a record representing a trigger
  for the builder. In this case, the 'E' event is converted to an 'I' event
  representing an instant in time (since the start time is unknown)

  Because CQ records for verifier_jobs_update actions will return all
  completed builds, the build_url is used to keep track of which builds
  have already completed, to store only one 'end' event for each build.
  """
  events = []
  completed_build_urls = set()
  for attempt_number, attempt in enumerate(attempts, start=1):
    open_builds = {}
    for record in attempt:
      events_in_attempt = record_to_events(record, attempt_number)
      for event in events_in_attempt:
        builder_key = event.builder_key()
        if event.is_meta():
          if builder_key in open_builds:
            open_builds[builder_key]['args'] = event.args
          continue
        event_dict = event.to_dict()
        if event.ph == 'B':
          if event.cat == 'Patch Progress' and builder_key in open_builds:
            # Ignore extra patch_starts and ready_to_commits.
            continue
          events.append(event_dict)
          open_builds[builder_key] = event_dict
        else:
          # First check whether there exists a 'B' event for the 'E' event
          # The 'E' event closes the build if it exists, convert the event to
          # an instant event if it doesn't exist.
          build_begin = open_builds.pop(builder_key, None)
          if not build_begin:
            event.ph = 'I'
            event_dict = event.to_dict()
          # Verifier repeatedly sends updates, only keep the first 'completed'
          # event and use build_url as unique identifier for events.
          build_url = event.args.get('build_url')
          if not build_url:
            action = event.args.get('action')
            if event.cat == 'Patch Progress' and action == 'patch_stop':
              for key in open_builds:
                open_event = open_builds[key]
                close_event = copy.deepcopy(open_event)
                close_event['ph'] = 'E'
                close_event['ts'] = event_dict['ts']
                close_event['args']['job_state'] = 'abandoned'
                close_event['cname'] = 'cq_build_abandoned'
                events.append(close_event)
            events.append(event_dict)
          elif build_url not in completed_build_urls:
            events.append(event_dict)
            completed_build_urls.add(build_url)
  return events


def record_to_events(record, attempt_number): # pragma: no cover
  """Given a single CQ record, creates a generator for Trace Viewer events.

  A single record in CQ can correspond to any number of events, depending on
  the action performed in the record. The conversion from each action to
  Trace Viewer event is listed below.

  patch_start: single 'B' event representing the start of the attempt.
  patch_ready_to_commit: single 'B' event representing start of commit attempt
  patch_committed: single 'E' event representing successful commit
  patch_failed: single 'E' event representing completed patch attempt
  patch_stop: single 'E' event representing the end of the attempt.
  verifier_trigger: multiple 'B' events, one for each builder triggered.
  verifier_jobs_update: multiple 'E' events, one for each builder success
    or failure.
  """
  action = record.fields.get('action')
  attempt_string = 'Attempt %d' % attempt_number
  timestamp = record.fields.get('timestamp')
  if action == 'verifier_trigger':
    masters = record.fields.get('trybots', {})
    for master in masters:
      for builder in masters[master]:
        yield TraceViewerEvent(builder, master, 'B', timestamp, attempt_string,
                               builder, 'cq_build_running')
  elif action == 'verifier_jobs_update':
    job_states = record.fields.get('jobs', {})
    # CQ splits jobs into lists based on their state.
    for cq_job_state, jobs in job_states.iteritems():
      # Jobs can be in many different states, JOB_STATE maps them to
      # 'running' or not.
      job_state = JOB_STATE.get(cq_job_state)

      if not job_state:
        continue
      elif job_state == 'running':
        for job_info in jobs:
          master = job_info['master']
          builder = job_info['builder']
          args = {'build_url': job_info.get('url')}
          yield MetaEvent(builder, master, args)
      else:
        for job_info in jobs:
          master = job_info['master']
          builder = job_info['builder']
          timestamp = rietveld_timestamp(job_info['timestamp'])
          cname = 'cq_build_' + job_state
          args = {
            'build_url': job_info.get('url'),
          }
          yield TraceViewerEvent(builder, master, 'E', timestamp, 
                                 attempt_string, builder, cname, args)
  elif action == 'patch_start':
    yield TraceViewerEvent(attempt_string, 'Patch Progress', 'B',
                           timestamp, attempt_string,
                           'Patch Progress', 'cq_build_attempt_running')
  elif action == 'patch_ready_to_commit':
    yield TraceViewerEvent('Patch Committing', 'Patch Progress', 'B',
                           timestamp, attempt_string,
                           'Patch Progress', 'cq_build_attempt_running')
  elif action == 'patch_committed':
    yield TraceViewerEvent('Patch Committing', 'Patch Progress', 'E',
                             timestamp, attempt_string,
                             'Patch Progress', 'cq_build_attempt_passed')
  elif action == 'patch_stop':
    cname = 'cq_build_attempt_'
    if 'successfully committed' in record.fields['message']:
      cname += 'passed'
    else:
      cname += 'failed'
    yield TraceViewerEvent(attempt_string, 'Patch Progress', 'E',
                           timestamp, attempt_string, 'Patch Progress',
                           cname, {'action': action})


class TraceViewerEvent(): # pragma: no cover
  """A class used to create JSON objects corresponding to an event.

  Trace Viewer requires a specific set of fields, described below:

  name: the name of the event, displayed as a label on the interval
  cat: category of the event, used with the search functionality
  ph: type of event. for CQ data, it will be 'B' or 'E' for begin or end
  ts: timestamp of event
  pid: process id, used for grouping threads
  tid: thread id, displayed to the left of all intervals with the same thread
  """
  def __init__(self, name, cat, ph, ts, pid, tid, cname, args=None):
    self.name = name
    self.cat = cat
    self.ph = ph
    self.ts = ts
    self.pid = pid
    self.tid = tid
    self.cname = cname
    self.args = args or {}

  def to_dict(self):
    return {
      'name': self.name,
      'cat': self.cat,
      'ph': self.ph,
      'ts': int(self.ts * 1000000),
      'pid': self.pid,
      'tid': self.tid,
      'cname': self.cname,
      'args': self.args
    }

  def builder_key(self):
    """Returns an identifier for the build of the form master/builder."""
    return self.cat + '/' + self.name

  def is_meta(self):
    return False


class MetaEvent(): # pragma: no cover
  """A class used to update TraceViewerEvents

  TraceViewer events may need to be modified after they have been created
  because the data for those events did not exist at time of creation. For
  example, build URLs are not included with verifier_triggers.
  """
  def __init__(self, name, cat, args):
    self.name = name
    self.cat = cat
    self.args = args

  def builder_key(self):
    return self.cat + '/' + self.name

  def is_meta(self):
    return True


def rietveld_timestamp(timestamp_string): # pragma: no cover
  """Converts a Rietveld timestamp into a unix timestamp."""
  try:
    return to_unix_timestamp(
        datetime.strptime(timestamp_string, RIETVELD_TIMESTAMP_FORMAT))
  except ValueError:
    return None
