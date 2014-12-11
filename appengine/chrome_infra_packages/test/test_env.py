# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prepares process state to run tests. Imported from all test files.

Bunch of hacks essentially to patch GAE code to run in unit tests environment.
"""

import contextlib
import os

# TODO(vadimsh): Figure out why this is required. Without it warmup test fails.
os.environ['APPLICATION_ID'] = 'test_app'
os.environ['SERVER_SOFTWARE'] = 'Development unittest'
os.environ['CURRENT_VERSION_ID'] = 'default-version.123'
