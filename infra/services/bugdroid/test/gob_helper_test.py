# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import infra.services.bugdroid.gob_helper as gob_helper


class GobHelperTest(unittest.TestCase):

  def test_ParseAuthenticatedRepo(self):
    auth_res, unauth_res = gob_helper.ParseAuthenticatedRepo(
        'https://chromium.googlesource.com/a/chromium/src.git')
    self.assertEqual('/a/chromium/src.git', auth_res.path)
    self.assertEqual('/chromium/src.git', unauth_res.path)
