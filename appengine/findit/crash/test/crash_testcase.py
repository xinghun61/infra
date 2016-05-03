# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from google.appengine.api import users

from common.findit_testcase import FinditTestCase
from model.crash.crash_config import CrashConfig


DEFAULT_CONFIG_DATA = {
    'fracas': {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'supported_platform_list_by_channel': {
            'canary': ['win', 'mac'],
            'supported_channel': ['supported_platform'],
        },
    }
}

class CrashTestCase(FinditTestCase):  # pragma: no cover.

  def setUp(self):
    super(CrashTestCase, self).setUp()
    CrashConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **DEFAULT_CONFIG_DATA)


