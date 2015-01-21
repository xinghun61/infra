# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains functions that know about CIPD client package layout."""

import logging

from . import processing
from . import reader


# Package name suffix -> location of cipd binary file.
CIPD_CLIENT_PACKAGES = {
  'infra/tools/cipd/linux-': 'cipd',
  'infra/tools/cipd/mac-': 'cipd',
  'infra/tools/cipd/windows-': 'cipd.exe',
}


# Name of ExtractCIPDClientProcessor. Also used from impl.py.
CIPD_BINARY_EXTRACT_PROCESSOR = 'cipd_client_binary:v1'


def is_cipd_client_package(package_name):
  """Returns True if |package_name| is cipd package with the client binary."""
  return any(package_name.startswith(p) for p in CIPD_CLIENT_PACKAGES)


def get_cipd_client_filename(package_name):
  """Returns filename of cipd client binary inside the cipd client package."""
  for prefix, binary in CIPD_CLIENT_PACKAGES.iteritems():
    if package_name.startswith(prefix):
      return binary
  raise ValueError('Not a CIPD client package')


class ExtractCIPDClientProcessor(processing.Processor):
  """Unzips CIPD client binary and uploads it to CAS."""

  def __init__(self, cas_service):
    super(ExtractCIPDClientProcessor, self).__init__()
    self.cas_service = cas_service
    self.name = CIPD_BINARY_EXTRACT_PROCESSOR

  def should_process(self, instance):
    return is_cipd_client_package(instance.package_name)

  def run(self, instance, data):
    assert self.should_process(instance)
    binary_name = get_cipd_client_filename(instance.package_name)

    logging.info('Opening the package...')
    try:
      src = data.open_packaged_file(binary_name)
    except reader.NoSuchPackagedFileError:
      raise processing.ProcessingError(
          'CIPD client binary "%s" was not found in the package' % binary_name)

    # Upload the binary to CAS store. Don't bother to check whether it is
    # already there since extracting the file from the package to calculate
    # its hash (to query CAS for presence) is as expensive as just overwriting
    # the file in CAS. In most cases it isn't there anyway.
    try:
      logging.info('Extracting "%s"...', binary_name)
      with self.cas_service.start_direct_upload('SHA1') as dst:
        while True:
          buf = src.read(512 * 1024)
          if not buf:
            break
          dst.write(buf)
          del buf
        hash_digest = dst.hash_digest
        data_length = dst.length
    finally:
      src.close()

    # Return the location of the extracted binary. If format of this dict
    # changes in a non backward compatible way, the version number in
    # CIPD_BINARY_EXTRACT_PROCESSOR should change too.
    # See impl.RepoService.get_client_binary_info for code that reads this data.
    return {
      'client_binary': {
        'size': data_length,
        'hash_algo': 'SHA1',
        'hash_digest': hash_digest,
      },
    }
