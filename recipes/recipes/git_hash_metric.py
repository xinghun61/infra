# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'recipe_engine/properties',
    'recipe_engine/python',
]


def RunSteps(api):
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
  yield (api.test('infra') +
         api.properties.git_scheduled(
           git_revision='deadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
           repository='https://chromium.googlesource.com/infra/infra'
         )
  )
