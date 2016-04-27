# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for ../git_cookie_daemon.py"""

import argparse
import infra_libs
import logging
import mock
import os
import requests
import tempfile
import unittest

from infra.services.git_cookie_daemon import git_cookie_daemon


class FakeLogger(object):
  def __init__(self):
    self.history = []

  def __getattr__(self, name):  # pragma: no cover
    def log(s, *args):  # pragma: no cover
      self.history.append(name + ': ' + (s % args))
    # This is a variable so coverage doesn't complain.
    names = ('info', 'debug', 'warning', 'error', 'exception')
    if name in names:  # pragma: no cover
      return log


class FakeRequestGetResponse(object):
  def __init__(self):
    pass

  def raise_for_status(self):
    pass

  def json(self):
    return {
      'expiresAt': 123,
      'accessToken': 'foo',
    }


class FakeRequestGet(object):
  def __init__(self):
    self.history = []

  def __call__(self, url, **kargs):
    self.history.append({'url': url, 'kargs': kargs})
    return FakeRequestGetResponse()


class GitCookieDaemonTests(unittest.TestCase):  # pragma: no cover
  def setUp(self):
    self.old_log = getattr(git_cookie_daemon, 'LOGGER')
    self.fake_log = FakeLogger()
    setattr(git_cookie_daemon, 'LOG', self.fake_log)

    self.old_get = getattr(requests, 'get')
    self.fake_get = FakeRequestGet()
    setattr(requests, 'get', self.fake_get)

    self.temp_dir = tempfile.mkdtemp()


  def tearDown(self):
    setattr(git_cookie_daemon, 'LOGGER', self.old_log)
    setattr(requests, 'get', self.old_get)
    infra_libs.rmtree(self.temp_dir)

  def result(self):
    return {
      'logs': self.fake_log.history,
      'urls': self.fake_get.history,
    }

  def test_configure(self):
    cookie_file = os.path.join(self.temp_dir, 'foo')
    daemon = git_cookie_daemon.GitCookieDaemon(
        cookie_file, 'bar', lambda _: None)
    with mock.patch.object(git_cookie_daemon, 'call'):
      daemon.configure()
    return self.result()

  def test_update_cookie(self):
    cookie_file = os.path.join(self.temp_dir, 'foo')
    daemon = git_cookie_daemon.GitCookieDaemon(
        cookie_file, 'bar', lambda _: None)
    with mock.patch.object(git_cookie_daemon, 'call'):
      daemon.update_cookie()
    return self.result()
