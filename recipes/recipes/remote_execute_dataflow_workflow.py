# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'build/puppet_service_account',
    'depot_tools/bot_update',
    'depot_tools/gclient',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/step',
]

PROPERTIES = {
  'workflow': Property(
      kind=str, help=('Path to the dataflow workflow you would like to '
                      'execute. Will be appended to the infra checkout path.')),
  'job_name': Property(
      kind=str, help=('Name that appears on the Dataflow console. Must match '
                      'the regular expression [a-z]([-a-z0-9]{0,38}[a-z0-9])')),
  'gcp_project_id': Property(
      kind=str, help=('Name of Google Cloud Project under which the Dataflow '
                      'job will be executed.')),
  'num_workers': Property(
      kind=int, default=3, help=('Number of GCE instances used to run job.')),
  'timeout': Property(
      kind=int, default=300, help=('Timeout, in seconds.')),
}

def RunSteps(api, workflow, job_name, gcp_project_id, num_workers, timeout):
  api.gclient.set_config('infra')
  bot_update_step = api.bot_update.ensure_checkout()
  api.gclient.runhooks()
  rev = bot_update_step.presentation.properties['got_revision']
  job_name = '%s-%s' % (job_name, rev)
  workflow_path = api.path['checkout']
  workflow_path = workflow_path.join(*workflow.split('/'))
  setup_path = api.path['checkout'].join('packages', 'dataflow', 'setup.py')
  python_path = api.path['checkout'].join('ENV', 'bin', 'python')
  # Clear PYTHONPATH since we want to use infra/ENV and not whatever the recipe
  # sets
  env = {'PYTHONPATH': '', 'GOOGLE_APPLICATION_CREDENTIALS':
         api.puppet_service_account.get_key_path('dataflow-launcher')}
  with api.context(env=env):
    cmd = [python_path, workflow_path,
           '--job_name', job_name,
           '--project', gcp_project_id,
           '--runner', 'DataflowRunner',
           '--setup_file', setup_path,
           '--staging_location', 'gs://dataflow-chrome-infra/events/staging',
           '--temp_location', 'gs://dataflow-chrome-infra/events/temp',
           '--save_main_session']
    if num_workers:
      cmd.extend(['--numWorkers', num_workers])
    api.step('Remote execute', cmd, timeout=timeout)

def GenTests(api):
  yield api.test('basic') + api.properties(
      workflow='packages/dataflow/cq_attempts.py', job_name='cq-attempts',
      gcp_project_id='chrome-infra-events', num_workers=5, timeout=60)
