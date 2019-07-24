# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'cloudkms',
  'recipe_engine/path',
]


def RunSteps(api):
  api.cloudkms.decrypt(
    'projects/PROJECT/locations/global/keyRings/KEYRING/cryptoKeys/KEY',
    api.path['start_dir'].join('ciphertext'),
    api.path['cleanup'].join('plaintext'),
  )
  # Decrypt another file; the module shouldn't install cloudkms again.
  api.cloudkms.decrypt(
    'projects/PROJECT/locations/global/keyRings/KEYRING/cryptoKeys/KEY',
    api.path['start_dir'].join('encrypted'),
    api.path['cleanup'].join('decrypted'),
  )


def GenTests(api):
  yield api.test('simple')
