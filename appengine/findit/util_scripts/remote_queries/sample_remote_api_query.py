# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An example of using Remote API to query datastore on live App Engine."""

import os
import sys

# Append path of Findit root directory to import remote_api.
_FINDIT_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)
sys.path.insert(0, _FINDIT_DIR)

# During importing, sys.path will be setup appropriately.
from local_libs import remote_api  # pylint: disable=W
# Set up the Remote API to use services on the live App Engine.
remote_api.EnableFinditRemoteApi()

from model.wf_step import WfStep

step = WfStep.Get('chromium.memory', 'Linux ASan Tests (sandboxed)', 11413,
                  'browser_tests')
with open('/tmp/step.log', 'w') as f:
  f.write(step.log_data)
