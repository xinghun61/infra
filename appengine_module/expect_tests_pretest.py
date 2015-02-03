# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=undefined-variable

# Crazy hack, because of appengine.
import os
import sys

# Using pretest_filename is magic, because it is available in the locals() of
# the script which execfiles this file.
# prefixing with 'pretest' to avoid name collisions in expect_tests.
pretest_APPENGINE_ENV_PATH = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(pretest_filename))))),
    'google_appengine')
sys.path.insert(0, pretest_APPENGINE_ENV_PATH)

import dev_appserver as pretest_dev_appserver
pretest_dev_appserver.fix_sys_path()
