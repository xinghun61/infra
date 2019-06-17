# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, MustRun, DropExpectation
from recipe_engine.recipe_api import Property

DEPS = [
    'build/docker',
    'depot_tools/bot_update',
    'depot_tools/gclient',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/runtime',
    'recipe_engine/service_account',
    'recipe_engine/step',
    'recipe_engine/time',
]


# Service account for push access to container registry, deployed by Puppet.
_CONTAINER_REGISTRY_CREDENTIAL_PATH = (
    '/creds/service_accounts/service-account-container_registry_pusher.json')
_CONTAINER_REGISTRY_PROJECT = 'chromium-container-registry'

PROPERTIES = {
    'arch_type': Property(
        kind=str,
        help='The CPU architecture [arm64, intel, etc.]',
        default=None
    ),
}


def RunSteps(api, arch_type):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()
  api.docker.ensure_installed()
  api.docker.get_version()

  # To prevent images from accumulating over time on the slave, delete old
  # images for the same container name.
  container_name = api.properties['container_name']
  with api.step.nest('clear old images'):
    get_images_step = api.docker(
        'images', '-q', '-f', 'reference=%s:*' % container_name,
        step_name='list images', stdout=api.raw_io.output(),
        step_test_data=lambda: api.raw_io.test_api.stream_output('img1'))
    image_ids = [line.strip() for line in get_images_step.stdout.splitlines()]
    for image_id in set(image_ids):
      try:
        api.docker(
          'rmi', '-f', image_id.strip(), step_name='delete image %s' % image_id)
      except api.step.StepFailure as f:
        f.result.presentation.status = api.step.WARNING

  # Run the build script. It assign a name to the resulting image and tags it
  # with 'latest'.
  dir_name = api.properties.get('dir_name', container_name)
  if arch_type:
    dir_name = dir_name + '_' + arch_type
  build_script = api.path['checkout'].join('docker', dir_name, 'build.sh')
  api.step('build image', ['/bin/bash', build_script])

  creds = api.service_account.from_credentials_json(
      _CONTAINER_REGISTRY_CREDENTIAL_PATH) if not api.runtime.is_luci else None
  api.docker.login(
      server='gcr.io', project='chromium-container-registry',
      service_account=creds)

  # Tag the image with the registry's url and the date.
  registry_url = 'gcr.io/%s' % _CONTAINER_REGISTRY_PROJECT
  date_tag = api.time.utcnow().strftime('%Y-%m-%d-%H-%M')
  registry_image_name = '%s/%s:%s' % (registry_url, container_name, date_tag)
  api.docker('tag', '%s:latest' % container_name, registry_image_name)

  # Push the image to the registry.
  upload_step = api.docker(
      'push', registry_image_name,
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output(
          '1-2-3: digest: sha256:deadbeef size:123'))
  image_spec = 'unknown'
  for line in upload_step.stdout.splitlines():
    if 'digest' in line:
      image_spec = 'image = ' + container_name + ':' + line.strip()
      break
  upload_step.presentation.step_text = image_spec


def GenTests(api):
  yield (
      api.test('full_build') +
      api.properties(
        container_name='android_docker',
        dir_name='android_devices',
        arch_type='ARM')
  )
  yield (
      api.test('full_build_luci') +
      api.properties(container_name='swarm_docker') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.post_process(DoesNotRun, 'get access token for '
                       'service-account-container_registry_pusher.json') +
      api.post_process(MustRun, 'get access token for default account') +
      api.post_process(DropExpectation)
  )
  yield (
      api.test('no_docker') +
      api.step_data('ensure docker installed', retcode=1)
  )
  yield (
      api.test('unknown_version') +
      api.properties(container_name='swarm_docker') +
      api.step_data('docker version', stdout=api.raw_io.output(''))
  )
  yield (
      api.test('failed_image_deletion') +
      api.properties(container_name='swarm_docker') +
      api.step_data('clear old images.delete image img1', retcode=1)
  )
