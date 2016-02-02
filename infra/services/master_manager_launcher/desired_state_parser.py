#!/usr/bin/python
# Copyright 2015 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Parse, validate and query the desired master state json."""

import bisect
import datetime
import json
import logging
import operator
import os
import re

from infra.libs.buildbot import master
from infra_libs.time_functions import timestamp
from infra_libs.time_functions import zulu
from infra.services.master_lifecycle import buildbot_state


LOGGER = logging.getLogger(__name__)


# A string that uniquely identifies the structure of a master state
# configuration file. Any changes made to the structure that are not backwards-
# compatible MUST update this value.
VERSION = '1'


class InvalidDesiredMasterState(ValueError):
  pass


def load_desired_state_file(filename):
  with open(filename) as f:
    return parse_desired_state(f.read())


def parse_desired_state(data):
  try:
    desired_state = json.loads(data)
  except ValueError as ex:
    LOGGER.exception('Failed to parse desired state JSON')
    raise InvalidDesiredMasterState(str(ex))

  try:
    validate_desired_master_state(desired_state)
  except InvalidDesiredMasterState as ex:
    LOGGER.error(ex.args[0])
    raise

  return desired_state


def validate_desired_master_state(desired_state):
  """Verify that the desired_master_state file is valid."""
  now = timestamp.utcnow_ts()

  version = desired_state.get('version', None)
  if version != VERSION:
    raise InvalidDesiredMasterState(
        "State version doesn't match current (%s != %s)" % (version, VERSION))

  master_states = desired_state.get('master_states', {})
  for mastername, states in master_states.iteritems():
    # Verify desired_state and timestamp are valid.
    for state in states:
      # Verify desired_state and transition_time_utc are present.
      for k in ('desired_state', 'transition_time_utc'):
        if not k in state:
          raise InvalidDesiredMasterState(
              'one or more states for master %s do not contain %s' % (
                  mastername, k))

      # Verify the desired state is in the allowed set.
      if (state['desired_state'] not in
          buildbot_state.STATES['desired_buildbot_state']):
        raise InvalidDesiredMasterState(
            'desired_state \'%s\' is not one of %s' %(
                state['desired_state'],
                buildbot_state.STATES['desired_buildbot_state']))

      # Verify the timestamp is Zulu time. Will raise an exception if invalid.
      state_time(state)

    # Verify the list is properly sorted.
    sorted_states = sorted(
        states, key=operator.itemgetter('transition_time_utc'))
    if sorted_states != states:
      raise InvalidDesiredMasterState(
          'master %s does not have states sorted by timestamp\n'
          'should be:\n%s' % (
              mastername,
              json.dumps(sorted_states, indent=2)))

    # Verify there is at least one state in the past.
    if not get_master_state(states, now=now):
      raise InvalidDesiredMasterState(
          'master %s does not have a state older than %s' % (mastername, now))

  master_params = desired_state.get('master_params', {})
  for mastername, params in master_params.iteritems():
    allowed_config_keys = set((
        'drain_timeout_sec',
        'builder_filters',
        ))
    extra_configs = set(params.iterkeys()) - allowed_config_keys
    if extra_configs:
      raise InvalidDesiredMasterState(
          'found unsupported configuration keys: %s' % (sorted(extra_configs),))

    if params.get('drain_timeout_sec') is not None:
      try:
        int(params['drain_timeout_sec'])
      except ValueError as e:
        raise InvalidDesiredMasterState(
            'invalid "drain_timeout_sec" for %s (%s): %s' % (
                mastername, params['drain_timeout_sec'], e))

    for builder_filter in params.get('builder_filters', []):
      try:
        re.compile(builder_filter)
      except re.error as e:
        raise InvalidDesiredMasterState(
            'invalid "builder_filters" entry for %s (%s): %s' % (
                mastername, builder_filter, e))


def get_master_state(states, now=None):
  """Returns the latest state earlier than the current (or specified) time.

  If there are three items, each with transition times of 100, 200 and 300:
    * calling when 'now' is 50 will return None
    * calling when 'now' is 150 will return the first item
    * calling when 'now' is 400 will return the third item
  """
  now = now or timestamp.utcnow_ts()

  times = [state_time(x) for x in states]
  index = bisect.bisect_left(times, now)
  if index > 0:  # An index of 0 means all timestamps are in the future.
    return states[index - 1]
  return None


def get_masters_for_host(desired_state, build_dir, hostname):
  """Identify which masters on this host should be managed.

  Returns triggered_masters and ignored_masters (a list and a set respectively).

  triggered_masters are masters on this host which have a corresponding entry in
  the desired_master_state file. Any master running assigned to this host that
  does *not* have an entry in the desired_master_state file is considered
  'ignored.'

  triggered_masters is a list of dicts. Each dict is the full dict from
  mastermap.py with two extra keys:
    - 'fulldir': the absolute path to the master directory
    - 'states': the state configuration for that master
    - 'params': any configured parameters for that master

  ignored_masters is a set of 'dirname' strings (ex: master.chromium).
  """
  master_states = desired_state.get('master_states', {})
  master_params = desired_state.get('master_params', {})

  triggered_masters = []
  ignored_masters = set()
  for master_dict in master.get_mastermap_for_host(
      build_dir, hostname):
    mastername = master_dict['dirname']
    if mastername in master_states:
      if master_dict['internal']:
        master_dir = os.path.abspath(os.path.join(
          build_dir, os.pardir, 'build_internal', 'masters',
          mastername))
      else:
        master_dir = os.path.abspath(os.path.join(
          build_dir, 'masters', mastername))
      master_dict['fulldir'] = master_dir
      master_dict['states'] = master_states[mastername]
      master_dict['params'] = master_params.get(mastername, {})

      triggered_masters.append(master_dict)
    else:
      ignored_masters.add(mastername)
  return triggered_masters, ignored_masters


def state_time(state):
  """Returns the transition time as float or raises an exception if invalid."""
  zt = zulu.parse_zulu_ts(state['transition_time_utc'])
  if zt is None:
    raise InvalidDesiredMasterState(
        'transition_time_utc \'%s\' is not Zulu time' % (
            state['transition_time_utc']))
  return zt


def prune_desired_state(desired_state, buffer_secs=3600):
  """Prune old desired_state entries.

  buffer_secs specifies how many seconds of buffer, only entries at least this
  many seconds in the past are considered for pruning.
  """
  cutoff = timestamp.utcnow_ts() - buffer_secs

  new_desired_state = {}

  for mastername, states in desired_state.iteritems():
    states_before_cutoff = []
    states_after_cutoff = []
    for state in states:
      # Verify the timestamp is a Zulu time.
      parsed_time = state_time(state)
      if parsed_time <= cutoff:
        states_before_cutoff.append(state)
      else:
        states_after_cutoff.append(state)

      # Verify there is at least one state in the past.
      if not states_before_cutoff:
        raise InvalidDesiredMasterState(
            'master %s does not have a state older than %s (%d secs ago)' % (
                mastername, cutoff, buffer_secs))

      new_desired_state[mastername] = (
          [max(states_before_cutoff, key=state_time)]
          + sorted(states_after_cutoff, key=state_time))

  return new_desired_state


def write_master_state(desired_state, filename):
  """Write a desired state file, removing old entries."""
  new_desired_state = {
      'master_params': desired_state.get('master_params', {}),
      'master_states': prune_desired_state(
          desired_state.get('master_states', {})),
      'version': VERSION,
  }
  with open(filename, 'w') as f:
    json.dump(
        new_desired_state, f, sort_keys=True, indent=2, separators=(',', ':'))
