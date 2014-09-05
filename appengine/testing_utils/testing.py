# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import inspect
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


def prevent_ndb_collisions():
  """This monkeypatches ndb's Model's _get_kind method to include the package.

  Normally, ndb uses class.__name__ as an identifier for object<->class mapping.
  This allows one to move model definitions around the application without
  breaking production data. However, it is unsuitable when testing multiple apps
  simultaneously (as expect_tests does), because two apps naming a model the
  same name will result in collisions (and incorrect tests). This method
  monkeypatches the _get_kind() method to include the package in which the
  class was defined -- guaranteeing there will be no collisions between apps.

  Additionally, it overrides __new__ on ndb.Key to prevent tests from using
  string-based types (ndb.Key('Project', ...) instead of ndb.Key(models.Project,
  ...)).
  """
  @classmethod
  def filename_kind(cls):
    """Disambiguates types in ndb's _kind_map by adding the class package."""
    return '%s.%s' % (inspect.getmodule(cls).__package__, cls.__name__)
  ndb.Model._get_kind = filename_kind

  @staticmethod
  def check_new(*args, **kwargs):  # pragma: no cover
    """Override ndb.Key's __new__ to prevent string-based types."""
    # First we call the real __new__ to get the newly created ndb.Key.
    new_obj = ndb.Key.__old__new__(*args, **kwargs)
    # Then we loop through the (kind, id) pairs to make sure each kind is in the
    # _kind_map. If it's not, that means that someone specified a string-based
    # key type, or it means someone loaded a module before loading testing.py.
    for (kind, _) in new_obj.pairs():
      # pylint: disable=W0212
      if kind not in ndb.Model._kind_map:
        raise TypeError(
            'The infra appengine test module does not support string ndb.Key '
            'types. Please use class-based types instead (models.Project '
            'instead of \'Project\'. The offending type is %s. This error may '
            'also be caused by not importing testing_utils.testing before '
            'importing models.' % (kind.split(':')[-1],))
    return new_obj

  # __new__ is specially cased to be a static method and somehow loses its
  # staticness when moved elsewhere. We wrap it in @staticmethod here.
  old_new = ndb.Key.__new__
  @staticmethod
  def wrapped_old_new(*args, **kwargs):  # pragma: no cover
    return old_new(*args, **kwargs)

  ndb.Key.__old__new__ = wrapped_old_new
  ndb.Key.__new__ = check_new


prevent_ndb_collisions()


class AppengineTestCase(auto_stub.TestCase): # pragma: no cover
  """Base class for Appengine test cases.

  Must set app_module to use self.test_app.
  """

  # To be set in tests that wants to use test_app
  app_module = None

  def setUp(self):
    super(AppengineTestCase, self).setUp()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
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
