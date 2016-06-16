# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import infra.services.bugdroid.scm_helper as scm_helper


class FakeLogEntry(object):

  def __init__(self, branch, scm):
    self.branch = branch
    self.scm = scm

class ScmHelperTest(unittest.TestCase):

  def test_GetBranch(self):
    le = FakeLogEntry('refs/heads/master', 'git')
    br_full = scm_helper.GetBranch(le, full=True)
    br_stripped = scm_helper.GetBranch(le, full=False)
    self.assertEqual('refs/heads/master', br_full)
    self.assertEqual('master', br_stripped)
