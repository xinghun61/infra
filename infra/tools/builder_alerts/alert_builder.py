# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import json
import logging
import re
import sys
import urllib

from infra.tools.builder_alerts import buildbot
from infra.tools.builder_alerts import reasons_splitter
from infra.tools.builder_alerts import string_helpers

# Python logging is stupidly verbose to configure.
def setup_logging():
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.DEBUG)
  handler = logging.StreamHandler()
  handler.setLevel(logging.DEBUG)
  formatter = logging.Formatter('%(levelname)s: %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  return logger, handler


log, logging_handler = setup_logging()

# Success or Warnings or None (didn't run) don't count as 'failing'.
NON_FAILING_RESULTS = (0, 1, None)


def compute_transition_and_failure_count(failure,
      failing_build, previous_builds):
  step_name = failure['step_name']
  reason = failure['reason']

  first_fail = failing_build
  last_pass = None
  fail_count = 1
  builds_missing_steps = []
  for build in previous_builds:
    matching_steps = [s for s in build['steps'] if s['name'] == step_name]
    if len(matching_steps) != 1:
      if not matching_steps:
        # This case is pretty common, so just warn all at once at the end.
        builds_missing_steps.append(build['number'])
      else:
        log.error("%s has unexpected number of %s steps: %s" % (
            build['number'], step_name, matching_steps))
      continue

    step = matching_steps[0]
    step_result = step['results'][0]
    if step_result not in NON_FAILING_RESULTS:
      if reason:
        reasons = reasons_for_failure(step, build,
          failure['builder_name'], failure['master_url'])
        # This build doesn't seem to have this step reason, ignore it.
        if not reasons:
          continue
        # Failed, but our failure reason wasn't present!
        # FIXME: This is wrong for compile failures, and possibly
        # for test failures as well if not all tests are run...
        if reason not in reasons:
          break

      first_fail = build
      fail_count += 1
      continue

    # None is 'didn't run', not a passing result.
    if step_result is None:
      continue

    last_pass = build
    break

  if builds_missing_steps:
    log.warn("Builds %s missing %s step" % (
        string_helpers.re_range(builds_missing_steps), step_name))

  return last_pass, first_fail, fail_count


def complete_steps_by_type(build):
  # Some builders use a sub-step pattern which just generates noise.
  # FIXME: This code shouldn't contain constants like these.
  IGNORED_STEP_NAMES = ['steps', 'trigger', 'slave_steps']
  steps = build['steps']
  complete_steps = [s for s in steps if s['isFinished']]

  ignored = [s for s in complete_steps
      if s['name'] in IGNORED_STEP_NAMES]
  not_ignored = [s for s in complete_steps
      if s['name'] not in IGNORED_STEP_NAMES]

  # 'passing' and 'failing' are slightly inaccurate
  # 'not_failing' and 'not_passing' would be more accurate, but harder to read.
  passing = [s for s in not_ignored
      if s['results'][0] in NON_FAILING_RESULTS]
  failing = [s for s in not_ignored
      if s['results'][0] not in NON_FAILING_RESULTS]

  return passing, failing, ignored


def failing_steps_for_build(build):
  if build.get('results') is None:
    log.error('Bad build: %s %s %s' % (build.get('number'),
        build.get('eta'), build.get('currentStep', {}).get('name')))
  # This check is probably not necessary.
  if build.get('results', 0) == 0:
    return []

  failing_steps = [step for step in build['steps']
      if step['results'][0] not in NON_FAILING_RESULTS]

  # Some builders use a sub-step pattern which just generates noise.
  # FIXME: This code shouldn't contain constants like these.
  IGNORED_STEPS = ['steps', 'trigger', 'slave_steps']
  return [step for step in failing_steps if step['name'] not in IGNORED_STEPS]


def reasons_for_failure(step, build, builder_name, master_url):
  splitter = reasons_splitter.splitter_for_step(step)
  if not splitter:
    return None
  return splitter.split_step(step, build, builder_name, master_url)


def alerts_from_step_failure(cache, step_failure, master_url, builder_name):
  build = buildbot.fetch_build_json(cache, master_url,
      builder_name, step_failure['build_number'])
  step = next((s for s in build['steps']
      if s['name'] == step_failure['step_name']), None)
  step_template = {
    'master_url': master_url,
    'last_result_time': step['times'][1],
    'builder_name': builder_name,
    'last_failing_build': step_failure['build_number'],
    'step_name': step['name'],
    'latest_revisions': buildbot.revisions_from_build(build),
  }
  alerts = []
  reasons = reasons_for_failure(step, build, builder_name, master_url)
  if not reasons:
    alert = dict(step_template)
    alert['reason'] = None
    alerts.append(alert)
  else:
    for reason in reasons:
      alert = dict(step_template)
      alert['reason'] = reason
      alerts.append(alert)

  return alerts


# FIXME: This should merge with compute_transition_and_failure_count.
def fill_in_transition(cache, alert, recent_build_ids):
  previous_build_ids = [num for num in recent_build_ids
      if num < alert['last_failing_build']]
  fetch_function = lambda num: buildbot.fetch_build_json(cache,
      alert['master_url'], alert['builder_name'], num)
  build = fetch_function(alert['last_failing_build'])
  previous_builds = map(fetch_function, previous_build_ids)

  last_pass_build, first_fail_build, fail_count = \
    compute_transition_and_failure_count(alert, build, previous_builds)

  failing = buildbot.revisions_from_build(first_fail_build)
  if last_pass_build:
    passing = buildbot.revisions_from_build(last_pass_build)
  else:
    passing = None

  alert.update({
    'failing_build_count': fail_count,
    'passing_build': last_pass_build['number'] if last_pass_build else None,
    'failing_build': first_fail_build['number'],
    'failing_revisions': failing,
    'passing_revisions': passing,
  })
  return alert


def find_current_step_failures(fetch_function, recent_build_ids):
  step_failures = []
  success_step_names = set()
  for build_id in recent_build_ids:
    build = fetch_function(build_id)
    passing, failing, _ = complete_steps_by_type(build)
    passing_names = set(map(lambda s: s['name'], passing))
    success_step_names.update(passing_names)
    for step in failing:
      if step['name'] in success_step_names:
        log.debug('%s passed more recently, ignoring.' % (step['name']))
        continue
      step_failures.append({
        'build_number': build_id,
        'step_name': step['name'],
      })
    # Bad way to check is-finished.
    if build['eta'] is None:
      break
    # log.debug('build %s incomplete, continuing search' % build['number'])
  return step_failures


def alerts_for_builder(cache, master_url, builder_name, recent_build_ids):
  recent_build_ids = sorted(recent_build_ids, reverse=True)
  # Limit to 100 to match our current cache-warming logic
  recent_build_ids = recent_build_ids[:100]

  fetch_function = lambda num: buildbot.fetch_build_json(cache,
      master_url, builder_name, num)
  step_failures = find_current_step_failures(fetch_function, recent_build_ids)

  # for failure in step_failures:
  #   print '%s from %s' % (failure['step_name'], failure['build_number'])

  alerts = []
  for step_failure in step_failures:
    alerts += alerts_from_step_failure(cache, step_failure,
        master_url, builder_name)
  return [fill_in_transition(cache, alert, recent_build_ids)
      for alert in alerts]


def alerts_for_master(cache, master_url, master_json, builder_name_filter=None):
  active_builds = []
  for slave in master_json['slaves'].values():
    for build in slave['runningBuilds']:
      active_builds.append(build)

  alerts = []
  for builder_name, builder_json in master_json['builders'].items():
    if builder_name_filter and builder_name_filter not in builder_name:
      continue
    # cachedBuilds will include runningBuilds.
    recent_build_ids = builder_json['cachedBuilds']

    buildbot.warm_build_cache(cache, master_url, builder_name,
        recent_build_ids, active_builds)
    alerts.extend(alerts_for_builder(cache, master_url,
        builder_name, recent_build_ids))

  return alerts


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument('builder_url', action='store')
  args = parser.parse_args(args)

  # https://build.chromium.org/p/chromium.win/builders/XP%20Tests%20(1)
  url_regexp = re.compile('(?P<master_url>.*)/builders/(?P<builder_name>.*)/?')
  match = url_regexp.match(args.builder_url)

  # FIXME: HACK
  CACHE_PATH = 'build_cache'
  cache = buildbot.BuildCache(CACHE_PATH)

  master_url = match.group('master_url')
  builder_name = urllib.unquote_plus(match.group('builder_name'))
  master_json = buildbot.fetch_master_json(master_url)
  # This is kinda a hack, but uses more of our existing code this way:
  alerts = alerts_for_master(cache, master_url, master_json, builder_name)
  print json.dumps(alerts, indent=1)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
