# Copyright (c) 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs git submodule daemon (gsubmodd) against a given source repo.

Intended to be called periodically (see CYCLE_TIME_SEC). Runs several iterations
of the daemon and then quits so that recipe has a chance to resync the source
code.
"""

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/gclient',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]

PROPERTIES = {
    'source_repo': Property(help='The URL of the repo to act on.'),
    'target_repo': Property(help='URL of mirror repo to be built/maintained.'),
    'limit': Property(help='Maximum number of commits to process per interval.',
                      default=''),
    'epoch': Property(
        help='(Hash of) existing commit after which to start mirror history.',
        default=''),
}

# How long to run. Should be in sync with buildbot scheduler period.
CYCLE_TIME_SEC = 10 * 60

# How many consecutive errors are tolerated before we quit with error.
MAX_ERROR_COUNT = 5


def RunSteps(api, source_repo, target_repo, limit='', epoch=''):
  # Checkout infra/infra solution.
  api.gclient.set_config('infra')
  api.gclient.c.solutions[0].revision = 'origin/deployed'
  api.gclient.checkout(timeout=10*60)
  api.gclient.runhooks()

  args = [
          'infra.services.gsubmodd',
          '--verbose',
          '--duration', str(CYCLE_TIME_SEC),
          '--max_errors', str(MAX_ERROR_COUNT),
          '--repo_dir', api.path['start_dir'].join('gsubmodd-work-dir'),
          '--target_repo', target_repo,
        ]
  if limit:
    args.extend(['--limit', limit])
  if epoch:
    args.extend(['--epoch', epoch])
  args.append(source_repo)

  api.python('gsubmodd', api.path['checkout'].join('run.py'), args)

def GenTests(api):
  yield (
    api.test('success') +
    api.properties(source_repo='https://example.com/chromium/src',
                   target_repo='https://example.com/experimental/codesearch') +
    api.step_data('gsubmodd', retcode=0)
  )
  yield (
    api.test('limited') +
    api.properties(source_repo='https://example.com/chromium/src',
                   limit='2000',
                   target_repo='https://example.com/experimental/codesearch') +
    api.step_data('gsubmodd', retcode=0)
  )
  yield (
    api.test('epoch') +
    api.properties(source_repo='https://example.com/chromium/src',
                   epoch='3c70abf6069f043037e9f932f62e0cb45e6592fe',
                   target_repo='https://example.com/experimental/codesearch') +
    api.step_data('gsubmodd', retcode=0)
  )
  yield (
    api.test('failure') +
    api.properties(source_repo='https://example.com/chromium/src',
                   target_repo='https://example.com/experimental/codesearch') +
    api.step_data('gsubmodd', retcode=1)
  )
