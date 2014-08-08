# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest

import infra
ROOT_PATH = os.path.abspath(os.path.dirname(infra.__file__))
GAE_PATH = os.path.join(ROOT_PATH, os.pardir, os.pardir, 'google_appengine')
sys.path.insert(0, GAE_PATH)

import webtest
from google.appengine.ext import testbed

import dev_appserver
dev_appserver.fix_sys_path()

class AppengineTestCase(unittest.TestCase): # pragma: no cover
  """Base class for Appengine test cases. Must set app_module for it to work."""
  def setUp(self):
    self.testapp = webtest.TestApp(self.app_module)
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

  def tearDown(self):
    self.testbed.deactivate()
