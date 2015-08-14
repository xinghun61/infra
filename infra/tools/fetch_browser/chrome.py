# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Library functions for fetching Chrome or Chromium."""

import logging
import requests
import tempfile
import zipfile
import os

# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)

OMAHA_URL = 'https://omahaproxy.appspot.com/all?os=%s&channel=%s'
GS_URL = ('https://storage.googleapis.com/chrome-unsigned'
             '/desktop-W15K3Y/%s/%s/chrome-%s.zip')

PLATFORM_MAPPING = {
    'linux2': {
        'omaha': 'linux',
        'cs_dir': 'precise64',
        'cs_filename': 'precise64',
        'chromepath': 'chrome-precise64/chrome',
    },
    'win32': {
        'omaha': 'win',
        'cs_dir': 'win',
        'cs_filename': 'win',
        'chromepath': 'chrome-win\\chrome.exe',
    },
    'darwin': {
        'omaha': 'mac',
        'cs_dir': 'mac64',
        'cs_filename': 'mac',
        'chromepath': ('chrome-mac/Google Chrome.app/'
                       'Contents/MacOS/Google Chrome'),
        'additional_paths': [
            ('chrome-mac/Google Chrome.app/Contents/Versions/%VERSION%/'
             'Google Chrome Helper.app/Contents/MacOS/Google Chrome Helper'),
        ],
    },
}

# This is actually covered, but python-coverage isn't picking it up.
def fetch_chrome(cache_dir, version, platform):  # pragma: no cover
  """Fetches Chrome from Google Storage.

  If the specific version of Chrome has been fetched already,
  then this does nothing.

  Chrome is fetched into [cache_dir]/chrome-<platform>-<version>/ where
  platform is [win|mac|linux] and version is the fully qualified version number.
  (ie. 42.0.2940.1).

  Version can be passed in as either the fully qualified version number or
  a channel string [stable|beta|dev|canary].  If a channel string is passed in
  then a query to ohamaproxy will always be made.
  """
  if version in ('stable', 'beta', 'dev', 'canary') :
    version = get_version_from_omaha(version, platform)
    LOGGER.info('Resolved version as %s' % version)
  platform_data = PLATFORM_MAPPING[platform]
  omaha_plat = platform_data['omaha']
  target_path = os.path.join(
      cache_dir, '-'.join(['chrome', omaha_plat, version]))
  chrome_path = os.path.join(target_path, platform_data['chromepath'])
  if os.path.exists(target_path):
    # TODO(hinoka): Verify installation
    LOGGER.info('Installation already exists in cache.')
    return chrome_path, version

  cs_url = GS_URL % (
      version, platform_data['cs_dir'], platform_data['cs_filename'])
  tmpdir = tempfile.mkdtemp()
  zip_path = os.path.join(tmpdir, 'chrome.zip')
  with open(zip_path, 'wb') as local_file:
    req = requests.get(cs_url)
    LOGGER.info('Downloading %s into %s' %(cs_url, zip_path))
    for block in req.iter_content(4096):
      local_file.write(block)
  with zipfile.ZipFile(zip_path) as zf:
    LOGGER.info('Unzipping %s into %s' % (zip_path, target_path))
    zf.extractall(path=target_path)
  if platform != 'win32':
    os.chmod(chrome_path, 0775)
  return chrome_path, version


# This is actually covered, but python-coverage isn't picking it up.
def get_version_from_omaha(version, platform):  # pragma: no cover
   platform_data = PLATFORM_MAPPING[platform]
   omaha_platform = platform_data['omaha']
   omaha_url = OMAHA_URL % (omaha_platform, version)
   response = requests.get(omaha_url).text
   return response.splitlines()[1].split(',')[2]

