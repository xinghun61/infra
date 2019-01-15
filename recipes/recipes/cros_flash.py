# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This recipe is used to flash a CrOS DUT on a Chromium bot.

This essentially calls out to the cros-sdk's flash tool (located at
https://codesearch.chromium.org/chromium/src/third_party/chromite/cli/flash.py).

That tool however has a dependency on the cros SDK's chroot (see
https://chromium.googlesource.com/chromiumos/docs/+/master/developer_guide.md#Create-a-chroot
for more info). Though it's often used in CrOS development, the chroot isn't
found in Chromium development at all, and has very limited support on Chromium
bots. Consequently, this recipe will take care of setting it up prior to
flashing the DUT. The basic steps of this recipe are:

- Fetch a full ChromiumOS checkout via repo. The checkout will be placed in a
  named cache for subsequent re-use.
- Build the chroot.
- Enter the chroot and flash the device.
"""

from recipe_engine import post_process

DEPS = [
  'build/chromite',
  'build/repo',
  'depot_tools/gsutil',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/tempfile',
]

# This is a special hostname that resolves to a different DUT depending on
# which swarming bot you're on.
CROS_DUT_HOSTNAME = 'variable_chromeos_device_hostname'

# Default password for root on a device running a test image. The contents of
# this password are public and not confidential.
CROS_SSH_PASSWORD = 'test0000'

# Path to an RSA key pair used for SSH auth with the DUT.
SWARMING_BOT_SSH_ID = '/b/id_rsa'


def RunSteps(api):
  gs_image_bucket = api.properties.get('gs_image_bucket')
  gs_image_path = api.properties.get('gs_image_path')
  if not gs_image_bucket or not gs_image_path:
    api.python.failing_step('unknown GS image URL',
        'Must pass the Google Storage URL for the image to flash via the '
        '"gs_image_bucket" and "gs_image_path" recipe properties.')

  # After flashing, the host's ssh identity is no longer authorized with the
  # DUT, so we'll need to add it back. The host's identity is an ssh key file
  # located at SWARMING_BOT_SSH_ID that the swarming bot generates at start-up.
  # Ensure that file exists on the bot.
  api.path.mock_add_paths(SWARMING_BOT_SSH_ID)
  api.path.mock_add_paths(SWARMING_BOT_SSH_ID + '.pub')
  if (not api.path.exists(SWARMING_BOT_SSH_ID) or
      not api.path.exists(SWARMING_BOT_SSH_ID + '.pub')):
    api.python.failing_step('host ssh ID not found',  # pragma: no cover
        'The env var CROS_SSH_ID_FILE_PATH (%s) must be set and point to a ssh '
        'key pair to use for authentication with the DUT.' % (
            SWARMING_BOT_SSH_ID))

  # Download (and optionally extract) the CrOS image in a temp dir.
  with api.tempfile.temp_dir("cros_flash") as tmp_dir:
    if gs_image_path.endswith('.tar.xz'):
      dest = tmp_dir.join('chromiumos_image.tar.xz')
      api.gsutil.download(
          gs_image_bucket, gs_image_path, dest, name='download image')
      with api.context(cwd=tmp_dir):
        extract_result = api.step(
            'extract image', ['/bin/tar', '-xvf', dest],
            stdout=api.raw_io.output('out'))
      # Pull the name of the exracted file from tar's stdout.
      img_path = tmp_dir.join(extract_result.stdout.strip())
    elif gs_image_path.endswith('.bin'):
      img_path = tmp_dir.join('chromiumos_image.bin')
      api.gsutil.download(
          gs_image_bucket, gs_image_path, img_path, name='download image')
    else:
      api.python.failing_step('unknown image format',
          'Image file must end in either ".bin" or ".tar.xz".')

    # Move into the named cache, and fetch a full ChromiumOS checkout.
    cros_checkout_path = api.path['cache'].join('builder')
    with api.context(cwd=cros_checkout_path):
      api.chromite.checkout(repo_sync_args=['-j4'])

      # Pass in --nouse-image below so the chroot is simply encased in a dir.
      # It'll otherwise try creating and mounting an image file (which can be a
      # 500GB sparse file).
      api.chromite.cros_sdk(
          'build chroot', ['exit'],
          chroot_cmd=cros_checkout_path.join('chromite', 'bin', 'cros_sdk'),
          args=['--nouse-image', '--create', '--debug'])

      # chromite's own virtual env setup conflicts with vpython, so temporarily
      # subvert vpython for the duration of the flash.
      with api.chromite.with_system_python():
        cros_tool_path = cros_checkout_path.join('chromite', 'bin', 'cros')
        arg_list = [
          'flash',
          CROS_DUT_HOSTNAME,
          img_path,
          '--disable-rootfs-verification',  # Needed to add ssh identity below.
          '--clobber-stateful',  # Fully wipe the device.
          '--force',  # Force yes to all Y/N prompts.
          '--debug',  # More verbose logging.
        ]
        api.python('flash DUT', cros_tool_path, arg_list)

  # Reauthorize the host's ssh identity with the DUT via ssh-copy-id, using
  # sshpass to pass in the root password.
  cmd = [
     '/usr/bin/sshpass',
     '-p', CROS_SSH_PASSWORD,
     '/usr/bin/ssh-copy-id', '-i', SWARMING_BOT_SSH_ID + '.pub',
     'root@' + CROS_DUT_HOSTNAME,
  ]
  api.step('reauthorize DUT ssh access', cmd)


def GenTests(api):
  yield (
    api.test('basic_test') +
    api.platform('linux', 64) +
    api.properties(
        gs_image_bucket='cros-image-bucket',
        gs_image_path='some/image/path.bin',
    ) +
    api.post_process(post_process.StatusSuccess) +
    api.post_process(post_process.DropExpectation)
  )

  yield (
    api.test('basic_test_with_extract') +
    api.platform('linux', 64) +
    api.properties(
        gs_image_bucket='cros-image-bucket',
        gs_image_path='some/image/path.tar.xz',
    ) +
    api.post_process(post_process.StatusSuccess) +
    api.post_process(post_process.DropExpectation)
  )

  yield (
    api.test('unknown_image_format') +
    api.platform('linux', 64) +
    api.properties(
        gs_image_bucket='cros-image-bucket',
        gs_image_path='some/image/path.exe',
    ) +
    api.post_process(post_process.StatusFailure) +
    api.post_process(post_process.DropExpectation)
  )

  yield (
    api.test('missing_props') +
    api.platform('linux', 64) +
    api.properties() +
    api.post_process(post_process.StatusFailure) +
    api.post_process(post_process.DropExpectation)
  )
