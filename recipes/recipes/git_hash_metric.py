# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'recipe_engine/buildbucket',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/runtime',
]


def RunSteps(api):
  if api.runtime.is_luci:
    gc = api.buildbucket.build_input.gitiles_commit
    git_revision = gc.id
    repository = 'https://%s/%s' % (gc.host, gc.project)
  else:
    # TODO(tandrii): remove this after builder is migrated to buildbot.
    git_revision = api.properties['git_revision']
    repository = api.properties['repository']

  api.python(
    'send hash to ts_mon',
    '/opt/infra-python/run.py',
    ['infra.tools.send_ts_mon_values',
     '--verbose',
     '--ts-mon-target-type=task',
     '--ts-mon-task-service-name=git_hash_metric',
     '--ts-mon-task-job-name=default',
     ('--string={"name":"repository/hash",'
      '"value":"%s","repository":"%s"}' % (git_revision, repository)),
   ]
  )


def GenTests(api):
  # TODO(tandrii): remove this after bug 790404 is complete.
  yield (api.test('infra_bbot') +
         api.properties.git_scheduled(
           git_revision='deadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
           repository='https://chromium.googlesource.com/infra/infra'
         )
  )
  yield (api.test('infra') +
         api.runtime(is_luci=True, is_experimental=False) +
         api.buildbucket.ci_build(
           'infra', 'cron',
           git_repo='https://chromium.googlesource.com/infra/infra',
           revision='deadbeefdeadbeefdeadbeefdeadbeefdeadbeef')
  )
