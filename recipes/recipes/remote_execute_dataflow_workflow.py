# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This recipe is used to execute Dataflow workflows.

If you want a workflow to run at regular intervals, you can configure a builder
to run this recipe. Dataflow workflows run on an internal builder, so this step
must be completed by a Google employee. Steps:
  1. Register builder in cr-buildbucket.cfg:  https://crrev.com/i/913671
  2. Set it to be triggered on some schedule: https://crrev.com/i/913672

Builders configured with the name matching "dataflow-workflow-.*" will be
automatically monitored for failures.

This recipe uses dataflow-launcher service account
`dataflow-launcher@chrome-infra-events.iam.gserviceaccount.com`.
It must have the permission to schedule a Dataflow job for your project.
"""

from recipe_engine.config import Single
from recipe_engine.recipe_api import Property

DEPS = [
  'build/puppet_service_account',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/step',

  'cloudkms',
]

PROPERTIES = {
  'workflow': Property(
      kind=str,
      help=('Path to the dataflow workflow you would like to '
            'execute. Will be appended to the infra checkout path. '
            'The path should begin with "packages/dataflow".')),
  'job_name': Property(
      kind=str,
      help=('Name that appears on the Dataflow console. Must match '
            'the regular expression [a-z]([-a-z0-9]{0,38}[a-z0-9])')),
  'gcp_project_id': Property(
      kind=str,
      help=('Name of Google Cloud Project under which the Dataflow '
            'job will be executed.')),
  'num_workers': Property(
      kind=Single((int, float)),
      default=3,
      help=('Number of GCE instances used to run job.')),
  'timeout': Property(
      kind=Single((int, float)),
      default=300,
      help=('Timeout, in seconds.')),
}


# The dataflow-launcher service account to be used with apache beam framework
# can only come in the form of refresh token (the framework doesn't allow for
# custom authentication mechanism, so we can't make use of ambient LUCI auth).
# Thus, we store it encrypted with Google Cloud KMS in assets/dataflow-launcher
# file, and when recipe runs it decrypts it using Cloud KMS. For this,
# the (LUCI) task service account under which the recipe is running must have
# been granted decrypt rights in Cloud KMS.
#
# How this was prepared:
#   1. Download private key file for a service account.
#   2. Create encrypted version:
#
#       $ gcloud kms encrypt \
#             --key=default \
#             --keyring=dataflow-launcher \
#             --location=global \
#             --project=chops-kms \
#             --ciphertext-file=assets/dataflow-launcher \
#             --plaintext-file=plaintext.json
#
#     You must have access to this key (ChOps troopers typically have it).

# If you ever want to get the privat key back:
#
#       $ gcloud kms decrypt \
#             --key=default \
#             --keyring=dataflow-launcher \
#             --location=global \
#             --project=chops-kms \
#             --plaintext-file=plaintext.json \
#             --ciphertext-file=assets/dataflow-launcher
#
# This recipe essentially does the above decryption command, but using
# LUCI cloudkms tool
# https://chromium.googlesource.com/infra/luci/luci-go/+/a6b2dd/client/cmd/cloudkms

# Name of the Cloud KMS key in format suitable for LUCI cloudkms tool.
KMS_CRYPTO_KEY = ('projects/chops-kms/locations/global/keyRings/'
                  'dataflow-launcher/cryptoKeys/default')
CREDS_FILE = 'dataflow-launcher'


def RunSteps(api, workflow, job_name, gcp_project_id, num_workers, timeout):
  num_workers = int(num_workers)
  timeout = int(timeout)

  api.gclient.set_config('infra')
  bot_update_step = api.bot_update.ensure_checkout()
  api.gclient.runhooks()
  rev = bot_update_step.presentation.properties['got_revision']
  job_name = '%s-%s' % (job_name, rev)
  workflow_path = api.path['checkout']
  workflow_path = workflow_path.join(*workflow.split('/'))
  setup_path = api.path['checkout'].join('packages', 'dataflow', 'setup.py')
  python_path = api.path['checkout'].join('ENV', 'bin', 'python')
  creds_path = api.path['cleanup'].join(CREDS_FILE + '.json')
  api.cloudkms.decrypt(
    KMS_CRYPTO_KEY,
    api.repo_resource('recipes', 'recipes', 'assets', CREDS_FILE),
    creds_path,
  )
  # Clear PYTHONPATH since we want to use infra/ENV and not whatever the recipe
  # sets
  env = {
    'PYTHONPATH': '',
    'GOOGLE_APPLICATION_CREDENTIALS': creds_path,
  }
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
  yield (
      api.test('basic')
      + api.properties(
          workflow='packages/dataflow/cq_attempts.py',
          job_name='cq-attempts',
          gcp_project_id='chrome-infra-events',
          num_workers=5,
          timeout=60)
  )
