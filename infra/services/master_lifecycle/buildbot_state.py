# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""A state machine to determine and act on a buildbot master's state."""


from infra.libs.state_machine import pattern_match
from infra.libs.time_functions import timestamp
from infra.libs.buildbot import master


STATES = {
  'buildbot': [
    'offline',
    'starting',
    'running',
    'draining',
    'drained',
    'crashed',
  ],
  'desired_buildbot_state': [
    'drained',
    'offline',
    'quitquitquit',
    'running',
  ],
  'desired_transition_time': [
    'ready_to_fire',
    'hold_steady',
  ],
}


def collect_evidence(master_directory, connection_timeout=30):
  """Collects evidence from the OS for late state determination."""
  evidence = {}
  evidence['now'] = timestamp.utcnow_ts()
  evidence['last_boot'] = master.get_last_boot(master_directory)
  evidence['last_no_new_builds'] = master.get_last_no_new_builds(
      master_directory)
  evidence['buildbot_is_running'] = master.buildbot_is_running(master_directory)

  if evidence['buildbot_is_running']:
    accepting_builds, current_running_builds = master.get_buildstate(
        master_directory, timeout=connection_timeout)
    evidence['accepting_builds'] = accepting_builds
    evidence['current_running_builds'] = current_running_builds

  return evidence


def construct_pattern_matcher(
    boot_timeout_sec=5 * 60, drain_timeout_sec=5 * 60, drain_build_thresh=0):
  # There is a bug in pylint which triggers false positives on decorated
  # decorators with arguments: http://goo.gl/Ln6uyn
  # pylint: disable=no-value-for-parameter
  matchlist = pattern_match.MatchList(STATES)

  @matchlist.add_match(
      buildbot='running',
      desired_buildbot_state='running',
      desired_transition_time='hold_steady')
  @matchlist.add_match(
      buildbot='drained',
      desired_buildbot_state='drained',
      desired_transition_time='hold_steady')
  @matchlist.add_match(
      buildbot='offline',
      desired_buildbot_state='offline')
  @matchlist.add_match(
      buildbot='offline',
      desired_buildbot_state='quitquitquit')
  @matchlist.add_match(
      buildbot='starting',
      exclusions={'desired_buildbot_state': ['offline', 'quitquitquit']})
  @matchlist.add_match(
      buildbot='draining',
      exclusions={'desired_buildbot_state': ['quitquitquit']})
  @matchlist.add_match(
      buildbot='crashed',
      exclusions={'desired_buildbot_state': ['offline', 'quitquitquit']})
  def _do_nothing():
    return []

  @matchlist.add_match(
      buildbot='drained',
      desired_buildbot_state='running')
  @matchlist.add_match(
      buildbot='drained',
      desired_buildbot_state='drained',
      desired_transition_time='ready_to_fire')
  def _make_restart():
    return [
        master.GclientSync, master.MakeStop, master.MakeWait, master.MakeStart]

  @matchlist.add_match(
      buildbot='running',
      desired_buildbot_state='running',
      desired_transition_time='ready_to_fire')
  @matchlist.add_match(
      buildbot='running',
      desired_buildbot_state='offline')
  @matchlist.add_match(
      buildbot='running',
      desired_buildbot_state='drained')
  def _make_no_new_builds():
    return [master.MakeNoNewBuilds]

  @matchlist.add_match(
      buildbot='offline',
      exclusions={
        'desired_buildbot_state': ['offline', 'quitquitquit'],
      })
  def _make_start():
    return [master.GclientSync, master.MakeStart]

  @matchlist.add_match(
      buildbot='crashed',
      desired_buildbot_state='offline')
  @matchlist.add_match(
      buildbot='starting',
      desired_buildbot_state='offline')
  @matchlist.add_match(
      buildbot='drained',
      desired_buildbot_state='offline')
  @matchlist.add_match(
      desired_buildbot_state='quitquitquit',
      exclusions={'buildbot': ['offline']})
  def _make_stop():
    return [master.MakeStop]

  @matchlist.add_detector('buildbot')
  def _check_buildbot_state(data):
    if not data['buildbot_is_running']:
      return 'offline'
    if (data['accepting_builds'] is None or
        data['current_running_builds'] is None):
      if data['last_boot'] > (data['now'] - boot_timeout_sec):
        return 'starting'
      return 'crashed'
    if data['accepting_builds']:
      return 'running'
    if data['current_running_builds'] <= drain_build_thresh:
      return 'drained'
    if data['last_no_new_builds'] > (data['now'] - drain_timeout_sec):
      return 'draining'
    return 'drained'

  @matchlist.add_detector('desired_buildbot_state')
  def _check_desired_state(data):
    desired_state = data['desired_buildbot_state']['desired_state']
    if desired_state in STATES['desired_buildbot_state']:
      return desired_state

    raise ValueError('%s is not a valid desired_buildbot_state' % desired_state)

  @matchlist.add_detector('desired_transition_time')
  def _check_transition_time(data):
    transition_time = data['desired_buildbot_state']['transition_time_utc']
    if transition_time > data['now']:
      # If we specify a date in the future and request 'running', the state
      # machine will continually reboot buildbot until that time is reached.
      raise ValueError(
          'specifying a date in the future creates ambiguity about now')
    if transition_time >= data['last_boot']:
      return 'ready_to_fire'
    return 'hold_steady'


  assert matchlist.is_correct
  return matchlist
