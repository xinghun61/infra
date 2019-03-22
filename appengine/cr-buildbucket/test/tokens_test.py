# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

import tokens


class BuildTokenTests(testing.AppengineTestCase):

  def test_roundtrip_simple(self):
    build_id = 1234567890
    task_key = 'task key'
    token = tokens.generate_build_token(build_id, task_key)
    tokens.validate_build_token(token, build_id, task_key)

  def test_roundtrip_no_task_key(self):
    build_id = 1234567890
    task_key = None
    token = tokens.generate_build_token(build_id, task_key)
    tokens.validate_build_token(token, build_id, task_key)
