# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import unittest

from infra_libs import luci_ctx
from infra_libs import utils


class ContextTest(unittest.TestCase):
  def setUp(self):
    super(ContextTest, self).setUp()
    luci_ctx._reset()

  def read(self, ctx_body, section):
    with utils.temporary_directory() as tempdir:
      ctx_file = os.path.join(tempdir, 'ctx.json')
      with open(ctx_file, 'w') as f:
        f.write(ctx_body)
      return luci_ctx.read(section, environ={'LUCI_CONTEXT': ctx_file})

  def test_no_ctx(self):
    self.assertIsNone(luci_ctx.read('key', environ={}))

  def test_loading_valid_ctx(self):
    self.assertEqual({'v': 'z'}, self.read(json.dumps({'k': {'v': 'z'}}), 'k'))
    self.assertEqual(None, self.read(json.dumps({'k': {'v': 'z'}}), 'unknown'))

  def test_not_json_ctx(self):
    with self.assertRaises(luci_ctx.Error):
      self.read('not json', 'k')

  def test_not_dict_ctx(self):
    with self.assertRaises(luci_ctx.Error):
      self.read('"not dict"', 'k')
