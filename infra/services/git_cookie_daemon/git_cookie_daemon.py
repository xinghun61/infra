# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Git_cookie_daemon."""

import argparse
import atexit
import cookielib
import functools
import logging
import logging.handlers
import os
import random
import requests
import shutil
import subprocess
import sys
import tempfile
import time

# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)
if sys.platform == 'win32':  # pragma: no cover
  GIT = 'C:\\setup\\depot_tools\\git.bat'
else:  # pragma: no cover
  GIT = '/usr/bin/git'

HOME_DIR = os.path.expanduser('~')
GIT_COOKIE_DIR = os.path.join(HOME_DIR, '.git-credential-cache')
GIT_COOKIE = os.path.join(GIT_COOKIE_DIR, 'cookie')
ACQUIRE_URL = ('http://169.254.169.254/0.1/meta-data/service-accounts/'
               'default/acquire')

COOKIE_SPEC = {
    'version': 0,
    'name': 'o',
    'port': None,
    'port_specified': False,
    'domain': '.googlesource.com',
    'domain_specified': True,
    'domain_initial_dot': True,
    'path': '/',
    'path_specified': True,
    'secure': True,
    'discard': False,
    'comment': None,
    'comment_url': None,
    'rest': None
}


class SubprocessFailed(Exception):
  pass


def call(args, cwd=None):  # pragma: no cover
  # Run subprocess correctly.
  args = [str(arg) for arg in args]
  LOGGER.info('Calling: %r', args)
  LOGGER.info('   in %s', cwd or os.getcwd())

  out = subprocess.PIPE
  proc = subprocess.Popen(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT)

  # Stream output to LOGGER.
  line = ''
  while True:
    buf = proc.stdout.read(1)
    if not buf:
      if line:
        LOGGER.debug(line)
      break
    if buf == '\n':
      LOGGER.debug(line)
      line = ''
    else:
      line += buf
  code = proc.wait()

  if code:
    LOGGER.error('%r exited with code %d', args[0], code)
  else:
    LOGGER.info('%r exited with code %d', args[0], code)
  if code:
    raise SubprocessFailed('%s failed with error %s' % (' '.join(args), code))




def ensure_git_cookie_daemon():  # pragma: no cover
  LOGGER.info('Setting up git cookie daemon')
  daemon = GitCookieDaemon(GIT_COOKIE, ACQUIRE_URL)
  daemon.configure()
  daemon.register_cleanup()
  while True:
    daemon.run()


class GitCookieDaemon(object):
  def __init__(self, cookie_file, acquire_url, sleep=None):
    self.cookie_file = cookie_file
    self.acquire_url = acquire_url
    self.expires = 0
    self.sleep = sleep or time.sleep

  def retry_on_error(self, num_retries, exception_type,
                     min_sleep=1, max_sleep=600):  # pragma: no cover
    """Decorator to retry on exception (with exponential backoff).

    Args:
      num_retries: maximum number of retries or None to retry forever.
      exception_type: exception class to catch and retry on.
      min_sleep: seconds to sleep between reties minimum.
      max_sleep: seconds to sleep between retries maximum.
    """
    def _real_decorator(fn):
      @functools.wraps(fn)
      def _wrapper(*args, **kwargs):
        tries = 0
        cur_sleep = min_sleep
        while True:
          tries += 1
          try:
            return fn(*args, **kwargs)
          except exception_type as e:  # pragma: no cover
            LOGGER.exception('Ran into exception %s', str(e))
            if num_retries is not None and tries > num_retries:
              LOGGER.error('It was the last attempt')
              raise
          LOGGER.info('Sleeping for %d seconds...', cur_sleep)
          self.sleep(cur_sleep)
          cur_sleep = min(cur_sleep * 2, max_sleep) + random.uniform(0, 1)
      return _wrapper
    return _real_decorator

  def configure(self):
    dirname = os.path.dirname(self.cookie_file)
    try:
      os.makedirs(dirname, 0700)
    except OSError:
      # If the directory exists.
      pass
    call([GIT, 'config', '--global', 'http.cookiefile', self.cookie_file])

  def _get_token(self):
    @self.retry_on_error(5, requests.exceptions.RequestException)
    def _inner():
      url = self.acquire_url
      LOGGER.debug('Acquiring git token from %s', url)
      r = requests.get(url, timeout=60)
      r.raise_for_status()
      return r.json()
    return _inner()

  def update_cookie(self):
    LOGGER.info('Updating Git Cookie')
    token = self._get_token()
    next_expires = token['expiresAt']

    fd, tmp_jar = tempfile.mkstemp(dir=os.path.dirname(self.cookie_file))
    os.close(fd)  # We just need the namespace, we don't need the fd.
    cookie_jar = cookielib.MozillaCookieJar(tmp_jar)
    cookie_jar.set_cookie(cookielib.Cookie(
      value=token['accessToken'],
      expires=next_expires,
      **COOKIE_SPEC))
    cookie_jar.save()
    shutil.move(tmp_jar, self.cookie_file)
    os.chmod(self.cookie_file, 0700)

    LOGGER.info('Git Cookie update success.  Next update %s', next_expires)
    # Refresh this 25 seconds before the next expiry
    self.expires = next_expires - 25

  def register_cleanup(self):  # pragma: no cover
    atexit.register(self.cleanup)

  def cleanup(self):  # pragma: no cover
    for filename in os.listdir(os.path.dirname(self.cookie_file)):
      full_path = os.path.join(os.path.dirname(self.cookie_file), filename)
      if os.path.exists(full_path):
        os.remove(full_path)

  def run(self):  # pragma: no cover
    now = time.time()
    expires = max(self.expires, now + 5)
    try:
      self.update_cookie()
    except Exception:
      LOGGER.exception('Failed to update git cookie')
    self.sleep(expires - now)
