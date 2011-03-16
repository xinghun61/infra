# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setups a local GAE instance to test against a live server for integration
tests.

It makes sure Google AppEngine SDK is found and starts the server on a free
inbound TCP port.
"""

import os
import socket
import subprocess
import time


class Failure(Exception):
  pass


def test_port(port):
  s = socket.socket()
  try:
    return s.connect_ex(('127.0.0.1', port)) == 0
  finally:
    s.close()


def find_free_port():
  """Finds an available port starting at 8080."""
  port = 8080
  max_val = (2<<16)
  while test_port(port) and port < max_val:
    port += 1
  if port == max_val:
    raise Failure('Having issues finding an available port')
  return port


class LocalGae(object):
  """Wraps up starting a GAE local instance for integration tests."""

  def __init__(self, base_dir=None, sdk_path=None):
    """base_dir defaults to .. from the file's directory."""
    # Paths
    self.base_dir = base_dir
    if not self.base_dir:
      self.base_dir = os.path.dirname(os.path.abspath(__file__))
      self.base_dir = os.path.realpath(os.path.join(self.base_dir, '..'))
    self.sdk_path = sdk_path or os.path.abspath(
        os.path.join(self.base_dir, '..', 'google_appengine'))
    self.dev_app = os.path.join(self.sdk_path, 'dev_appserver.py')
    self.instance_path = os.path.join(self.base_dir)
    self.test_server = None
    self.port = None
    # Generate a friendly environment.
    self.env = os.environ.copy()
    self.env['LANGUAGE'] = 'en'

  def install_prerequisites(self):
    # First, verify the Google AppEngine SDK is available.
    if not os.path.isfile(self.dev_app):
      raise Failure('Install google_appengine sdk in %s' % self.sdk_path)

  def start_server(self, verbose=False):
    self.install_prerequisites()
    self.port = find_free_port()
    if verbose:
      stdout = None
      stderr = None
    else:
      stdout = subprocess.PIPE
      stderr = subprocess.PIPE
    self.test_server = subprocess.Popen(
        [self.dev_app,
          self.base_dir,
          '--port=%d' % self.port,
          '--datastore_path=' + os.path.join(self.base_dir, 'tmp.db'),
          '--use_sqlite',
          '-c'],
        stdout=stdout, stderr=stderr, env=self.env)
    # Loop until port 127.0.0.1:port opens or the process dies.
    while not test_port(self.port):
      self.test_server.poll()
      if self.test_server.returncode is not None:
        raise Failure(
            'Test GAE instance failed early on port %s' %
            self.port)
      time.sleep(0.001)

  def stop_server(self):
    if self.test_server:
      self.test_server.kill()
      self.test_server = None
      self.port = None

# vim: ts=2:sw=2:tw=80:et:
