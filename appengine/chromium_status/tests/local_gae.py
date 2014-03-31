# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setups a local GAE instance to test against a live server for integration
tests.

It makes sure Google AppEngine SDK is found and starts the server on a free
inbound TCP port.
"""

import cookielib
import errno
import logging
import os
import re
import socket
import subprocess
import tempfile
import time
import sys
import urllib
import urllib2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GAE_SDK = None


def _load_modules():
  """Loads all the necessary modules.

  Update sys.path to be able to import chromium-status and GAE SDK.
  """
  global GAE_SDK
  if GAE_SDK:
    return
  root_dir = BASE_DIR
  # First, verify the Google AppEngine SDK is available.
  while True:
    if os.path.isfile(os.path.join(root_dir, 'google_appengine', 'VERSION')):
      break
    next_root = os.path.dirname(root_dir)
    if next_root == root_dir:
      raise Failure(
          'Install google_appengine sdk in %s' % os.path.dirname(BASE_DIR))
    root_dir = next_root
  GAE_SDK = os.path.realpath(os.path.join(root_dir, 'google_appengine'))
  # Need yaml later.
  gae_sdk_lib = os.path.realpath(os.path.join(GAE_SDK, 'lib'))
  sys.path.insert(0, os.path.realpath(os.path.join(gae_sdk_lib, 'yaml', 'lib')))


class Failure(Exception):
  pass


def test_port(port):
  s = socket.socket()
  try:
    return s.connect_ex(('127.0.0.1', port)) == 0
  finally:
    s.close()


def find_free_port(base_port=8080):
  """Finds an available port starting at 8080."""
  port = base_port
  max_val = (2<<16)
  while test_port(port) and port < max_val:
    port += 1
  if port == max_val:
    raise Failure('Having issues finding an available port')
  return port


class LocalGae(object):
  """Wraps up starting a GAE local instance for integration tests."""

  def __init__(self, base_dir=None):
    """base_dir defaults to .. from the file's directory."""
    # Paths
    self.base_dir = base_dir
    if not self.base_dir:
      self.base_dir = os.path.dirname(os.path.abspath(__file__))
      self.base_dir = os.path.realpath(os.path.join(self.base_dir, '..'))
    self.test_server = None
    self.port = None
    self.admin_port = None
    self.app_id = None
    self.url = None
    self.admin_url = None
    self.tmp_db = None
    self._xsrf_token = None
    self._cookie_jar = cookielib.CookieJar()
    cookie_processor = urllib2.HTTPCookieProcessor(self._cookie_jar)
    redirect_handler = urllib2.HTTPRedirectHandler()
    self._opener = urllib2.build_opener(redirect_handler, cookie_processor)

  def install_prerequisites(self):
    # Load GAE SDK.
    _load_modules()

    # Now safe to import GAE SDK modules.
    # Unable to import 'yaml'
    # pylint: disable=F0401

    import yaml
    self.app_id = yaml.load(
        open(os.path.join(self.base_dir, 'app.yaml'), 'r'))['application']
    logging.debug('Instance app id: %s' % self.app_id)
    assert self.app_id

  def start_server(self, verbose=False):
    self.install_prerequisites()
    self.port = find_free_port()
    self.admin_port = find_free_port(base_port=self.port + 1)
    if verbose:
      stdout = None
      stderr = None
    else:
      stdout = subprocess.PIPE
      stderr = subprocess.PIPE
    # Generate a friendly environment.
    env = os.environ.copy()
    env['LANGUAGE'] = 'en'
    h, self.tmp_db = tempfile.mkstemp(prefix='local_gae')
    os.close(h)
    cmd = [
        sys.executable,
        os.path.join(GAE_SDK, 'dev_appserver.py'),
        self.base_dir,
        '--port', str(self.port),
        '--admin_port', str(self.admin_port),
        '--datastore_path', self.tmp_db,
        '--datastore_consistency_policy', 'consistent',
        '--skip_sdk_update_check',
    ]
    if verbose:
      cmd.extend([
          '--log_level', 'debug',
      ])
    self.test_server = subprocess.Popen(
        cmd, stdout=stdout, stderr=stderr, env=env)
    # Loop until port 127.0.0.1:port opens or the process dies.
    while not test_port(self.port):
      while not test_port(self.admin_port):
        self.test_server.poll()
        if self.test_server.returncode is not None:
          raise Failure(
              'Test GAE instance failed early on port %s' %
              self.port)
        time.sleep(0.001)
    self.url = 'http://localhost:%d/' % self.port
    self.admin_url = 'http://localhost:%d/' % self.admin_port

  def stop_server(self):
    if self.test_server:
      try:
        self.test_server.terminate()
      except OSError as e:
        if e.errno != errno.ESRCH:
          raise
      self.test_server = None
      self.port = None
      self.url = None
      self.admin_url = None
      if self.tmp_db:
        try:
          os.remove(self.tmp_db)
        except OSError:
          pass
        self.tmp_db = None

  def get(self, suburl, url=None):
    if url is None:
      url = self.url
    logging.debug('GET: %r', url + suburl)
    request = urllib2.Request(url + suburl)
    f = self._opener.open(request)
    data = f.read()
    return data

  def post(self, suburl, data, url=None):
    if url is None:
      url = self.url
    logging.debug('POST(%r): %r', url + suburl, data)
    request = urllib2.Request(url + suburl, urllib.urlencode(data))
    f = self._opener.open(request)
    return f.read()

  def clear_cookies(self):
    self._cookie_jar.clear()

  def login(self, username, admin):
    try:
      self.get('_ah/login?email=%s&admin=%r&action=login&continue=/' % (
          urllib.quote_plus(username), admin))
    except urllib2.HTTPError:
      # Ignore http errors as the continue url may be inaccessible.
      pass

  def query(self, cmd):
    """Lame way to modify the db remotely on dev server.

    Using remote_api inside the unit test is a bit too invasive.
    """
    data = {
        'code': 'from google.appengine.ext import db\n' + cmd,
        'module_name': 'default',
        'xsrf_token': self.xsrf_token,
    }
    return self.post('console', data, url=self.admin_url)

  @property
  def xsrf_token(self):
    if self._xsrf_token is None:
      self.clear_cookies()
      interactive = self.get('console', url=self.admin_url)
      match = re.search(r"'xsrf_token': *'(.*?)'", interactive)
      if not match:
        logging.debug('interactive console output:\n%s', interactive)
        raise Failure('could not find xsrf_token')
      self._xsrf_token = match.group(1)
      self.clear_cookies()
    return self._xsrf_token

# vim: ts=2:sw=2:tw=80:et:
