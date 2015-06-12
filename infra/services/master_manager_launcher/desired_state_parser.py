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

from infra.libs.buildbot import master
from infra.libs.time_functions import timestamp
from infra.libs.time_functions import zulu
from infra.services.master_lifecycle import buildbot_state


LOGGER = logging.getLogger(__name__)


class InvalidDesiredMasterState(ValueError):
  pass


def load_desired_state_file(filename):
  with open(filename) as f:
    return parse_desired_state(f.read())


def parse_desired_state(data):
  try:
    desired_state = json.loads(data)
  except ValueError:
    raise InvalidDesiredMasterState()
  if not desired_master_state_is_valid(desired_state):
    raise InvalidDesiredMasterState()
  return desired_state


def parse_transition_time(transition_time):
  """Parses an int, float, or Zulu time. Returns a float timestamp or None."""
  if isinstance(transition_time, (int, float)):
    return float(transition_time)
  return zulu.parse_zulu_ts(transition_time)


def desired_master_state_is_valid(desired_state):
  """Verify that the desired_master_state file is valid."""
  now = timestamp.utcnow_ts()

  for mastername, states in desired_state.iteritems():
    # Verify desired_state and timestamp are valid.
    for state in states:
      # Verify desired_state and transition_time_utc are present.
      for k in ('desired_state', 'transition_time_utc'):
        if not k in state:
          LOGGER.error(
              'one or more states for master %s do not contain %s',
              mastername, k)
          return False

      # Verify the desired state is in the allowed set.
      if (state['desired_state'] not in
          buildbot_state.STATES['desired_buildbot_state']):
        LOGGER.error(
            'desired_state \'%s\' is not one of %s',
            state['desired_state'],
            buildbot_state.STATES['desired_buildbot_state'])
        return False

      # Verify the timestamp is a number or Zulu time.
      if parse_transition_time(state['transition_time_utc']) is None:
        LOGGER.error(
            'transition_time_utc \'%s\' is not an int, float, or Zulu time',
            state['transition_time_utc'])
        return False

    # Verify the list is properly sorted.
    sorted_states = sorted(
        states, key=operator.itemgetter('transition_time_utc'))
    if sorted_states != states:
      LOGGER.error('master %s does not have states sorted by timestamp',
          mastername)
      LOGGER.error('should be:\n%s', json.dumps(sorted_states, indent=2))
      return False

    # Verify there is at least one state in the past.
    if not get_master_state(states, now=now):
      LOGGER.error(
          'master %s does not have a state older than %s', mastername, now)
      return False

  return True


def get_master_state(states, now=None):
  """Returns the latest state earlier than the current (or specified) time.

  If there are three items, each with transition times of 100, 200 and 300:
    * calling when 'now' is 50 will return None
    * calling when 'now' is 150 will return the first item
    * calling when 'now' is 400 will return the third item
  """
  now = now or timestamp.utcnow_ts()

  times = [parse_transition_time(x['transition_time_utc']) for x in states]
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
  mastermap.py with two extra keys: 'fulldir' (the absolute path to the master
  directory), and 'states' (a list of desired states sorted by transition time,
  pulled from the desired states file).

  ignored_masters is a set of 'dirname' strings (ex: master.chromium).
  """
  triggered_masters = []
  ignored_masters = set()
  for master_dict in master.get_mastermap_for_host(
      build_dir, hostname):
    if master_dict['dirname'] in desired_state:
      if master_dict['internal']:
        master_dir = os.path.abspath(os.path.join(
          build_dir, os.pardir, 'build_internal', 'masters',
          master_dict['dirname']))
      else:
        master_dir = os.path.abspath(os.path.join(
          build_dir, 'masters', master_dict['dirname']))
      master_dict['fulldir'] = master_dir
      master_dict['states'] = desired_state[master_dict['dirname']]

      triggered_masters.append(master_dict)
    else:
      ignored_masters.add(master_dict['dirname'])
  return triggered_masters, ignored_masters
