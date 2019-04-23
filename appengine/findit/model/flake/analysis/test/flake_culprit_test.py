# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from gae_libs.testcase import TestCase

from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis


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

  def testGetCulpritLink(self):
    culprit = FlakeCulprit.Create('chromium', 'r1', 123)
    self.assertEqual(
        'https://analysis.chromium.org/p/chromium/flake-portal/analysis/'
        'culprit?key=%s' % culprit.key.urlsafe(), culprit.GetCulpritLink())

  def testGenerateRevertReason(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 2, 's', 't')
    analysis.original_step_name = 's'
    analysis.original_test_name = 't'
    analysis.put()
    culprit = FlakeCulprit.Create('chromium', 'r1', 123)
    culprit.flake_analysis_urlsafe_keys = [analysis.key.urlsafe()]

    expected_reason = textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
        culprit for flakes in the build cycles as shown on:
        https://analysis.chromium.org/p/chromium/flake-portal/analysis/culprit?key=%s\n
        Sample Failed Build: %s\n
        Sample Failed Step: s\n
        Sample Flaky Test: t""") % (
        123,
        culprit.key.urlsafe(),
        'https://ci.chromium.org/buildbot/m/b/2',
    )

    self.assertEqual(expected_reason,
                     culprit.GenerateRevertReason('m/b/2', 123, 'r123', 's'))
