# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import random
import time

from google.appengine.api import memcache


_MEMCACHE_MASTER_DOWNLOAD_LOCK = 'master-download-lock-%s'
_MEMCACHE_MASTER_DOWNLOAD_EXPIRATION_SECONDS = 60 * 60
_DOWNLOAD_INTERVAL_SECONDS = 10


def WaitUntilDownloadAllowed(
    master_name, timeout_seconds=90):  # pragma: no cover
  """Waits until next download from the specified master is allowed.

  Returns:
    True if download is allowed to proceed.
    False if download is not still allowed when the given timeout occurs.
  """
  client = memcache.Client()
  key = _MEMCACHE_MASTER_DOWNLOAD_LOCK % master_name

  deadline = time.time() + timeout_seconds
  while True:
    info = client.gets(key)
    if not info or time.time() - info['time'] >= _DOWNLOAD_INTERVAL_SECONDS:
      new_info = {
          'time': time.time()
      }
      if not info:
        success = client.add(
            key, new_info, time=_MEMCACHE_MASTER_DOWNLOAD_EXPIRATION_SECONDS)
      else:
        success = client.cas(
            key, new_info, time=_MEMCACHE_MASTER_DOWNLOAD_EXPIRATION_SECONDS)

      if success:
        logging.info('Download from %s is allowed. Waited %s seconds.',
                     master_name, (time.time() + timeout_seconds - deadline))
        return True

    if time.time() > deadline:
      logging.info('Download from %s is not allowed. Waited %s seconds.',
                   master_name, timeout_seconds)
      return False

    logging.info('Waiting to download from %s', master_name)
    time.sleep(_DOWNLOAD_INTERVAL_SECONDS + random.random())
