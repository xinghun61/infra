# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Modifies sys.path to include all packages necessary to run tests.

Must be imported by all tests to setup the environment.
"""

import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Setup os.environ as if running on GAE.
os.environ.update({
  'SERVER_SOFTWARE': 'Development blah/1.0',
  'APPLICATION_ID': 'chromium-git-access',
  'CURRENT_VERSION_ID': 'default-version.377973721559728128',
  'CURRENT_MODULE_ID': 'default',
})

# Modify sys.path to include GAE packages.
from appengine.utils import testing   # pylint: disable=W0611

# Include components third party.
sys.path.insert(0, os.path.join(APP_DIR, 'components', 'third_party'))
# Include app itself, so imports relative to app root work.
sys.path.insert(0, APP_DIR)
