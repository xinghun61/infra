# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.flake.flake_culprit import FlakeCulprit


class FlakeculpritTest(TestCase):

  def testCreate(self):
    repo_name = 'chromium'
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    culprit = FlakeCulprit.Create(repo_name, revision, commit_position, url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)
    self.assertEqual(commit_position, culprit.commit_position)
    self.assertEqual(url, culprit.url)
