# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import re

import gae_ts_mon
from google.appengine.api import users

from gae_libs.testcase import TestCase
from libs.gitiles.change_log import ChangeLog
from libs.http import retry_http_client
from model.crash.crash_config import CrashConfig


DEFAULT_CONFIG_DATA = {
    'fracas': {
        'analysis_result_pubsub_topic': 'projects/project-name/topics/name',
        'supported_platform_list_by_channel': {
            'canary': ['win', 'mac', 'linux'],
            'supported_channel': ['supported_platform'],
        },
        'platform_rename': {'linux': 'unix'},
        'signature_blacklist_markers': ['Blacklist marker'],
        'top_n': 7
    },
    'component_classifier': {
        'path_function_component': [
            [
                'src/comp1.*',
                '',
                'Comp1>Dummy'
            ],
            [
                'src/comp2.*',
                'func2.*',
                'Comp2>Dummy'
            ],
        ],
        'top_n': 4
    },
    'project_classifier': {
        'project_path_function_hosts': [
            ['android_os', ['googleplex-android/'], ['android.'], None],
            ['chromium', None, ['org.chromium'], ['src/']]
        ],
        'non_chromium_project_rank_priority': {
            'android_os': '-1',
            'others': '-2',
        },
        'top_n': 4
    }
}

DUMMY_CHANGELOG = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
    ],
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})



class PredatorTestCase(TestCase):  # pragma: no cover.

  def setUp(self):
    super(PredatorTestCase, self).setUp()
    CrashConfig.Get().Update(
        users.User(email='admin@chromium.org'), True, **DEFAULT_CONFIG_DATA)
    gae_ts_mon.reset_for_unittest(disable=True)

  def GetDummyChangeLog(self):
    return DUMMY_CHANGELOG
