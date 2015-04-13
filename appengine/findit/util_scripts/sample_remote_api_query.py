# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An example of using Remote API to query datastore on live App Engine."""

import remote_api  # During importing, sys.path will be setup appropriately.
from model.wf_step import WfStep


# Set up the Remote API to use services on the live App Engine.
remote_api.EnableRemoteApi(app_id='findit-for-me')

step = WfStep.Get('chromium.memory', 'Linux ASan Tests (sandboxed)', 11413,
                  'browser_tests')
with open('/tmp/step.log', 'w') as f:
  f.write(step.log_data)
