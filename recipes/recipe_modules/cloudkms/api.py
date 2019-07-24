# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class CloudKMSApi(recipe_api.RecipeApi):
  """API for interacting with CloudKMS using the LUCI cloudkms tool."""

  def __init__(self, **kwargs):
    super(CloudKMSApi, self).__init__(**kwargs)
    self._cloudkms_bin = None

  @property
  def cloudkms_path(self):
    """Returns the path to LUCI cloudkms binary.

    When the property is accessed the first time, cloudkms will be installed
    using cipd.
    """
    if self._cloudkms_bin is None:
      cloudkms_dir = self.m.path['start_dir'].join('cloudkms')
      self.m.cipd.ensure(
          cloudkms_dir, {'infra/tools/luci/cloudkms/${platform}': 'latest'})
      self._cloudkms_bin = cloudkms_dir.join('cloudkms')
    return self._cloudkms_bin

  def decrypt(self, kms_crypto_key, input_file, output_file):
    """Decrypt a ciphertext file with a CloudKMS key.

    Args:
      * kms_crypto_key (str) - The name of the encryption key, e.g.
        projects/chops-kms/locations/global/keyRings/[KEYRING]/cryptoKeys/[KEY]
      * input_file (Path) - The path to the input (ciphertext) file.
      * output_file (Path) - The path to the output (plaintext) file. It is
        recommended that this is inside api.path['cleanup'] to ensure the
        plaintext file will be cleaned up by recipe.
    """
    self.m.step('decrypt', [
        self.cloudkms_path, 'decrypt',
        '-input', input_file,
        '-output', output_file,
        kms_crypto_key,
    ])
