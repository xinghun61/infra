# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs git subtree daemon (gsubtreed) against Chromium src repo.

Intended to be called periodically (see CYCLE_TIME_SEC). Runs several iteration
of the daemon and then quits so that recipe has a chance to resync the source
code.
"""

import urlparse

from recipe_engine.config import Single
from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/gclient',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

PROPERTIES = {
  'target_repo': Property(
      kind=str,
      help='Which repo to work with. Required.'),
  'cycle_time_sec': Property(
      default=10*60, kind=Single((int, float)),
      help='How long to run gsubtreed for.'),
  'max_error_count': Property(
      default=5, kind=Single((int, float)),
      help='How many consecutive errors are tolerated before gsubtreed '
           'quits with error'),
}


def RunSteps(api, target_repo, cycle_time_sec, max_error_count):
  assert target_repo
  cycle_time_sec = max(0, int(cycle_time_sec))
  max_error_count = max(0, int(max_error_count))

  # Checkout infra/infra solution.
  solution_path = api.path['cache'].join('builder', 'solution')
  api.file.ensure_directory('init cache if not exists', solution_path)
  with api.context(cwd=solution_path):
    api.gclient.set_config('infra')
    api.gclient.c.solutions[0].revision = 'origin/deployed'
    api.gclient.checkout(timeout=10*60)
    api.gclient.runhooks()

  env = {}
  # github.com apparently has a hard time with our user agents.
  if urlparse.urlparse(target_repo).hostname.endswith('github.com'):
    env['GIT_USER_AGENT'] = None

  # Run the daemon for CYCLE_TIME_SEC seconds.
  # TODO(iannucci): Make infra.run a module
  try:
    with api.context(env=env):
      api.python(
          'gsubtreed',
          solution_path.join('infra', 'run.py'),
          [
            'infra.services.gsubtreed',
            '--verbose',
            '--duration', str(cycle_time_sec),
            '--max_errors', str(max_error_count),
            '--repo_dir',
            api.path['cache'].join('builder', 'gsubtreed-work-dir'),
            '--json_output', api.json.output(add_json_log=False),
            target_repo,
          ])
  finally:
    step_result = api.step.active_result
    # Add a list of generates commits to the build page.
    if step_result.json.output:
      path_counts = step_result.json.output['summary']
      step_result.presentation.step_text = '</br></br>'
      step_result.presentation.step_text += '</br>'.join(
        '%s: %s' % (path, num) for path, num in path_counts.iteritems() if num
      )
      total = sum(path_counts.values())
      step_result.presentation.step_summary_text = 'commits: %d' % total


def GenTests(api):
  json_output = {
    'error_count': 2,
    'summary': {
      'some/path': 5,
      'some': 10,
      'other': 0,
    }
  }

  yield (
    api.test('success') +
    api.properties(target_repo='https://host.googlesource.com/my/repo') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=0)
  )
  yield (
    api.test('failure') +
    api.properties(target_repo='https://host.googlesource.com/my/repo') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=1)
  )
  yield (
    api.test('alt') +
    api.properties(target_repo='https://host.googlesource.com/my/repo',
                   cycle_time_sec=3600,
                   max_error_count=60) +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=0)
  )
  yield (
    api.test('github_env_var') +
    api.properties(target_repo='https://github.com/sweet/repo') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=0)
  )
