# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import json
import logging
import multiprocessing
import os
import re
import sys
import traceback
import urllib

from infra.tools.builder_alerts import buildbot
from infra.tools.builder_alerts import reasons_splitter
from infra.tools.builder_alerts import string_helpers


# Success or Warnings or None (didn't run) don't count as 'failing'.
NON_FAILING_RESULTS = (0, 1, None)


def compute_transition(cache, alert, recent_build_ids):  # pragma: no cover
  master = alert['master_url']
  builder = alert['builder_name']
  step = alert['step_name']
  reason = alert['reason']

  previous_build_ids = [num for num in recent_build_ids
      if num < alert['last_failing_build']]
  fetch_function = lambda num: buildbot.fetch_build_json(
      cache, master, builder, num)
  first_fail = fetch_function(alert['last_failing_build'])
  previous_builds = map(fetch_function, previous_build_ids)

  last_pass = None
  builds_missing_steps = []
  for build in previous_builds:
    matching_steps = [s for s in build['steps'] if s['name'] == step]
    if len(matching_steps) != 1:
      if not matching_steps:
        # This case is pretty common, so just warn all at once at the end.
        builds_missing_steps.append(build['number'])
      else:
        logging.error("%s has unexpected number of %s steps: %s" % (
            build['number'], step, matching_steps))
      continue

    step = matching_steps[0]
    step_result = step['results'][0]
    if step_result not in NON_FAILING_RESULTS:
      if reason:
        reasons = reasons_for_failure(cache, step, build, builder, master)
        # This build doesn't seem to have this step reason, ignore it.
        if not reasons:
          continue
        # Failed, but our failure reason wasn't present!
        # FIXME: This is wrong for compile failures, and possibly
        # for test failures as well if not all tests are run...
        if reason not in reasons:
          last_pass = build
          break

      first_fail = build
      continue

    # None is 'didn't run', not a passing result.
    if step_result is None:
      continue

    last_pass = build
    break

  if builds_missing_steps:
    logging.warn("Builds %s missing %s step" % (
        string_helpers.re_range(builds_missing_steps), step))

  return last_pass, first_fail


def complete_steps_by_type(build):
  steps = build['steps']
  complete_steps = [s for s in steps if s['isFinished']]

  # 'passing' and 'failing' are slightly inaccurate
  # 'not_failing' and 'not_passing' would be more accurate, but harder to read.
  passing = [s for s in complete_steps
      if s['results'][0] in NON_FAILING_RESULTS]
  failing = [s for s in complete_steps
      if s['results'][0] not in NON_FAILING_RESULTS]

  return passing, failing


def failing_steps_for_build(build):  # pragma: no cover
  if build.get('results') is None:
    logging.error('Bad build: %s %s %s' % (build.get('number'),
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


def reasons_for_failure(cache, step, build, builder_name, master_url):
  master_name = buildbot.master_name_from_url(master_url)
  cache_key = os.path.join(master_name, builder_name, str(build['number']),
        '%s.json' % step['name'])
  if cache.has(cache_key):
    return cache.get(cache_key)
  splitter = reasons_splitter.splitter_for_step(step)
  if not splitter:
    return None
  reasons = splitter.split_step(step, build, builder_name, master_url)
  cache.set(cache_key, reasons)
  return reasons


def alerts_from_step_failure(cache, step_failure, master_url,
    builder_name):  # pragma: no cover
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
  reasons = reasons_for_failure(cache, step, build, builder_name, master_url)
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


def generate_alert_key(master, builder, step, reason):  # pragma: no cover
  return '%s.%s.%s.%s' % (master, builder, step, reason)


def fill_in_transition(cache, alert, recent_build_ids,
    old_alerts):  # pragma: no cover
  master = alert['master_url']
  builder = alert['builder_name']
  step = alert['step_name']
  reason = alert['reason']
  alert_key = generate_alert_key(master, builder, step, reason)

  if alert_key in old_alerts:
    logging.debug('Using old alert data. master: %s, builder: %s, step: %s,'
        ' reason: %s' % (master, builder, step, reason))
    update_data = { k: old_alerts[alert_key][k] for k in [
        'passing_build', 'failing_build', 'failing_revisions',
        'passing_revisions']}
  else:
    logging.debug('Computing new alert data. master: %s, builder: %s, step: %s,'
        ' reason: %s' % (master, builder, step, reason))

    last_pass_build, first_fail_build = \
      compute_transition(cache, alert, recent_build_ids)

    failing = buildbot.revisions_from_build(first_fail_build)
    if last_pass_build:
      passing = buildbot.revisions_from_build(last_pass_build)
    else:
      passing = None

    update_data = {
      'passing_build': last_pass_build['number'] if last_pass_build else None,
      'failing_build': first_fail_build['number'],
      'failing_revisions': failing,
      'passing_revisions': passing,
    }

  alert.update(update_data)
  return alert


def find_current_step_failures(fetch_function, recent_build_ids):
  step_failures = []
  completed_step_names = set()

  for build_id in recent_build_ids:
    build = fetch_function(build_id)
    passing, failing = complete_steps_by_type(build)

    passing_names = set(map(lambda s: s['name'], passing))
    completed_step_names.update(passing_names)

    for step in failing:
      name = step['name']

      if name in completed_step_names:
        logging.debug('%s ran more recently, ignoring.' % (name))
        continue

      # Add this here so that the if-check above doesn't skip failures
      # from the current build we're processing.
      completed_step_names.add(name)

      step_failures.append({
        'build_number': build_id,
        'step_name': name,
      })

    if not buildbot.is_in_progress(build):
      break

  # Some builders use a sub-step pattern which just generates noise.
  # FIXME: This code shouldn't contain constants like these.
  IGNORED_STEP_NAMES = ['steps', 'trigger', 'slave_steps']

  ignored_failures = [s for s in step_failures
      if s['step_name'] in IGNORED_STEP_NAMES]
  non_ignored_failures = [s for s in step_failures
      if s['step_name'] not in IGNORED_STEP_NAMES]

  if len(non_ignored_failures):
    return non_ignored_failures
  return ignored_failures


def alerts_for_builder(cache, master_url, builder_name,
    recent_build_ids, old_alerts):  # pragma: no cover
  recent_build_ids = sorted(recent_build_ids, reverse=True)
  # Limit to 100 to match our current cache-warming logic
  recent_build_ids = recent_build_ids[:100]

  fetch_function = lambda num: buildbot.fetch_build_json(cache,
      master_url, builder_name, num)
  step_failures = find_current_step_failures(fetch_function, recent_build_ids)

  alerts = []
  for step_failure in step_failures:
    alerts += alerts_from_step_failure(cache, step_failure,
        master_url, builder_name)
  return [fill_in_transition(cache, alert, recent_build_ids, old_alerts)
      for alert in alerts]


def alerts_for_master(cache, master_url, master_json, old_alerts,
    builder_name_filter=None, jobs=1):  # pragma: no cover
  active_builds = []
  for slave in master_json['slaves'].values():
    for build in slave['runningBuilds']:
      active_builds.append(build)


  def process_builder(builder_name):
    try:
      builder_json = master_json['builders'][builder_name]
      if builder_name_filter and builder_name_filter not in builder_name:
        return None

      # cachedBuilds will include runningBuilds.
      recent_build_ids = builder_json['cachedBuilds']

      buildbot.warm_build_cache(cache, master_url, builder_name,
          recent_build_ids, active_builds)
      return alerts_for_builder(cache, master_url, builder_name,
          recent_build_ids, old_alerts)
    except:
      # Put all exception text into an exception and raise that so it doesn't
      # get eaten by the multiprocessing code.
      raise Exception("".join(traceback.format_exception(*sys.exc_info())))

  pool = multiprocessing.dummy.Pool(processes=jobs)
  builder_alerts = pool.map(process_builder, master_json['builders'].keys())
  pool.close()
  pool.join()

  alerts = []
  for alert in builder_alerts:
    if alert:
      alerts.extend(alert)

  return alerts


def main(args):  # pragma: no cover
  logging.basicConfig(level=logging.DEBUG)

  parser = argparse.ArgumentParser()
  parser.add_argument('builder_url', action='store')
  args = parser.parse_args(args)

  # https://build.chromium.org/p/chromium.win/builders/XP%20Tests%20(1)
  url_regexp = re.compile('(?P<master_url>.*)/builders/(?P<builder_name>.*)/?')
  match = url_regexp.match(args.builder_url)

  # FIXME: HACK
  CACHE_PATH = 'build_cache'
  cache = buildbot.DiskCache(CACHE_PATH)

  master_url = match.group('master_url')
  builder_name = urllib.unquote_plus(match.group('builder_name'))
  master_json = buildbot.fetch_master_json(master_url)
  # This is kinda a hack, but uses more of our existing code this way:
  alerts = alerts_for_master(cache, master_url, master_json, builder_name)
  print json.dumps(alerts, indent=1)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
