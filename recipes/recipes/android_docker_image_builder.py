# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


DEPS = [
    'build/file',
    'depot_tools/bot_update',
    'depot_tools/gclient',
    'recipe_engine/path',
    'recipe_engine/raw_io',
    'recipe_engine/step',
    'recipe_engine/time',
]


# Service account for push access to container registry, deployed by Puppet.
_CONTAINER_REGISTRY_CREDENTIAL_PATH = (
    '/creds/service_accounts/service-account-container_registry_pusher.json')
_CONTAINER_REGISTRY_PROJECT = 'chromium-container-registry'


def RunSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  # Ensure docker is installed.
  # FIXME: Move docker logic here into its own module if it's ever worth it.
  try:
    find_docker_step = api.step(
        'Find docker bin', ['which', 'docker'], stdout=api.raw_io.output(),
        step_test_data=lambda: api.raw_io.test_api.stream_output(
            '/usr/bin/docker'))
  except api.step.StepFailure as f:
    f.result.presentation.step_text = (
        'Error: is docker installed on this machine?')
    raise
  docker_bin = find_docker_step.stdout.strip()

  # Get version.
  docker_version_step = api.step(
      'Get docker version', [docker_bin, 'version'], stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output(
          'Version: 1.2.3'))
  for line in docker_version_step.stdout.splitlines():
    if 'Version' in line:
      docker_version_step.presentation.step_text = line.strip()
      break
  else:
    docker_version_step.presentation.step_text = 'Version unknown?'

  # To prevent images from accumulating over time on the slave, dumbly delete
  # all local images. This has the unfortunate side effect of making every build
  # a full clobber, but this recipe shouldn't be run too frequently and doesn't
  # require fast cycle times.
  # TODO(bpastene): Be smarter about this.
  with api.step.nest('Clear all local images'):
    get_images_step = api.step(
        'Get images', [docker_bin, 'images', '-q'], stdout=api.raw_io.output(),
        step_test_data=lambda: api.raw_io.test_api.stream_output('img1'))
    for image_id in get_images_step.stdout.splitlines():
      try:
        api.step(
            'Delete image %s' % image_id,
            [docker_bin, 'rmi', '-f', image_id.strip()])
      except api.step.StepFailure as f:
        f.result.presentation.status = api.step.WARNING

  # Run the build script. It names the resulting image 'android_docker' and
  # tags it with 'latest'.
  build_script = api.path['checkout'].join(
      'docker', 'android_devices', 'build.sh')
  api.step('Build image', ['/bin/bash', build_script])

  # Read service account creds.
  service_account_creds = api.file.read(
      'Read service account creds', _CONTAINER_REGISTRY_CREDENTIAL_PATH)

  # Login to the container registry. Pass the contents of the credentials file
  # as the password. Probably want to run this only internally.
  # See https://cloud.google.com/container-registry/docs/advanced-authentication
  login_cmd = [
      docker_bin, 'login',
      '-u', '_json_key',
      '-p', '%s' % service_account_creds,
      'https://gcr.io'
  ]
  api.step('Login to registry', login_cmd)

  # Tag the image with the registry's url and the date.
  registry_url = 'gcr.io/%s' % _CONTAINER_REGISTRY_PROJECT
  date_tag = api.time.utcnow().strftime('%Y-%m-%d-%H-%M')
  registry_image_name = '%s/android_docker:%s' % (registry_url, date_tag)
  tag_cmd = [
      docker_bin,
      'tag',
      'android_docker:latest',
      registry_image_name
  ]
  api.step('Tag image', tag_cmd)

  # Push the image to the registry.
  upload_step = api.step(
      'Push image', [docker_bin, 'push', registry_image_name],
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output(
          '1-2-3: digest: sha256:deadbeef size:123'))
  image_spec = 'unknown'
  for line in upload_step.stdout.splitlines():
    if 'digest' in line:
      image_spec = 'image = android_docker:' + line.strip()
      break
  upload_step.presentation.step_text = image_spec


def GenTests(api):
  yield (api.test('full_build'))
  yield (
      api.test('no_docker') +
      api.step_data('Find docker bin', retcode=1)
  )
  yield (
      api.test('unknown_version') +
      api.step_data('Get docker version', stdout=api.raw_io.output(''))
  )
  yield (
      api.test('failed image deletion') +
      api.step_data('Clear all local images.Delete image img1', retcode=1)
  )
