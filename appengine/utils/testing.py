# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

import infra
ROOT_PATH = os.path.abspath(os.path.dirname(infra.__file__))
GAE_PATH = os.path.join(ROOT_PATH, os.pardir, os.pardir, 'google_appengine')
sys.path.insert(0, GAE_PATH)

import dev_appserver
dev_appserver.fix_sys_path()

from google.appengine.ext import ndb
from google.appengine.ext import testbed

import webtest
from testing_support import auto_stub


class AppengineTestCase(auto_stub.TestCase): # pragma: no cover
  """Base class for Appengine test cases.

  Must set app_module to use self.test_app.
  """

  # To be set in tests that wants to use test_app
  app_module = None

  def setUp(self):
    super(AppengineTestCase, self).setUp()
    tb = testbed.Testbed()
    tb.setup_env(current_version_id='testbed.version')
    tb.activate()
    self.testbed = tb
    # Can't use init_all_stubs() because PIL isn't in wheel.
    self.testbed.init_app_identity_stub()
    self.testbed.init_blobstore_stub()
    self.testbed.init_capability_stub()
    self.testbed.init_channel_stub()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_files_stub()
    self.testbed.init_logservice_stub()
    self.testbed.init_mail_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_taskqueue_stub()
    self.testbed.init_urlfetch_stub()
    self.testbed.init_user_stub()
    self.testbed.init_xmpp_stub()
    # Test app is lazily initialized on a first use from app_module.
    self._test_app = None

  def tearDown(self):
    try:
      self.testbed.deactivate()
    finally:
      super(AppengineTestCase, self).tearDown()

  @property
  def test_app(self):
    """Returns instance of webtest.TestApp that wraps app_module."""
    if self._test_app is None:
      # app_module may be a property, so access it only once.
      app = self.app_module
      if app is None:
        self.fail('self.app_module is not provided by the test class')
      self._test_app = webtest.TestApp(app)
    return self._test_app

  def mock_now(self, now):
    """Mocks time in ndb properties that use auto_now and auto_now_add.

    Args:
      now: instance of datetime.datetime.
    """
    self.mock(ndb.DateTimeProperty, '_now', lambda _: now)
    self.mock(ndb.DateProperty, '_now', lambda _: now.date())

  def mock_current_user(self, user_id='', user_email='', is_admin=False):
    # dev_appserver hack.
    self.testbed.setup_env(
      USER_ID=user_id,
      USER_EMAIL=user_email,
      USER_IS_ADMIN=str(int(is_admin)),
      overwrite=True)
