# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import re

from google.appengine.api import users

from common.change_log import ChangeLog
from common.findit_testcase import FinditTestCase
from model.crash.crash_config import CrashConfig


DEFAULT_CONFIG_DATA = {
    'fracas': {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'supported_platform_list_by_channel': {
            'canary': ['win', 'mac', 'linux'],
            'supported_channel': ['supported_platform'],
        },
    },
    'component_classifier': {
        "path_function_component": [
            [
              "src/comp1.*",
              "",
              "Comp1>Dummy"
            ],
            [
              "src/comp2.*",
              "func2.*",
              "Comp2>Dummy"
            ],
        ],
        "top_n": 4
    },
    'project_classifier': {
        "file_path_marker_to_project_name": {
            "googleplex-android/": "android_os",
        },
        "function_marker_to_project_name": {
            "org.chromium": "chromium",
            "android.": "android_os",
        },
        "host_directories": [
            "src/"
        ],
        "non_chromium_project_rank_priority": {
            "android_os": "-1",
            "others": "-2",
        },
        "top_n": 4
    }
}

DUMMY_CHANGELOG = ChangeLog.FromDict({
    'author_name': 'r@chromium.org',
    'message': 'dummy',
    'committer_email': 'r@chromium.org',
    'commit_position': 175900,
    'author_email': 'r@chromium.org',
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
    ],
    'author_time': 'Thu Mar 31 21:24:43 2016',
    'committer_time': 'Thu Mar 31 21:28:39 2016',
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'committer_name': 'example@chromium.org',
    'revision': '1',
    'reverted_revision': None
})


class CrashTestCase(FinditTestCase):  # pragma: no cover.

  def setUp(self):
    super(CrashTestCase, self).setUp()
    CrashConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **DEFAULT_CONFIG_DATA)

  def GetDummyChangeLog(self):
    return DUMMY_CHANGELOG
