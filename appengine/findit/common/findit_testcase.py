# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from testing_utils import testing


class FinditTestCase(testing.AppengineTestCase):
  # Setup the customized queues.
  taskqueue_stub_root_path = os.path.join(
    os.path.dirname(__file__), os.path.pardir)
