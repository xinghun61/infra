# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.isolated_target import IsolatedTarget


class IsolatedTargetTest(TestCase):

  def setUp(self):
    super(IsolatedTargetTest, self).setUp()
    for pos in range(100):
      entry = IsolatedTarget.Create(843400990909000 + pos, 'chromium', 'ci',
                                    'chromium.linux', 'Linux Builder',
                                    'chromium.googlesource.com', 'chromium/src',
                                    'refs/heads/master', '', 'browser_tests',
                                    'abcdef%dabcdef' % pos, 55000 + pos * 13)
      entry.put()

  def testFindIsolate(self):
    before = IsolatedTarget.FindIsolateBeforeCommitPositionByBucket(
        'chromium', 'ci', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(before[0], IsolatedTarget.Get('abcdef49abcdef'))
    at = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByBucket(
        'chromium', 'ci', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(at[0], IsolatedTarget.Get('abcdef50abcdef'))
    after = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByBucket(
        'chromium', 'ci', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55655)
    self.assertEqual(after[0], IsolatedTarget.Get('abcdef51abcdef'))

  def testFindIsolateByMaster(self):
    before = IsolatedTarget.FindIsolateBeforeCommitPositionByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(before[0], IsolatedTarget.Get('abcdef49abcdef'))
    at = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(at[0], IsolatedTarget.Get('abcdef50abcdef'))
    after = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55655)
    self.assertEqual(after[0], IsolatedTarget.Get('abcdef51abcdef'))

  def testIsolatedHash(self):
    isolated_hash = 'isolated_hash'
    target = IsolatedTarget.Create(10000, 'chromium', 'ci', 'chromium.linux',
                                   'Linux Builder', 'chromium.googlesource.com',
                                   'chromium/src', 'refs/heads/master', '',
                                   'browser_tests', isolated_hash, 55000)
    self.assertEqual(isolated_hash, target.isolated_hash)

  def testBuildUrl(self):
    build_id = 10000
    target = IsolatedTarget.Create(build_id, 'chromium', 'ci', 'chromium.linux',
                                   'Linux Builder', 'chromium.googlesource.com',
                                   'chromium/src', 'refs/heads/master', '',
                                   'browser_tests', 'a1b2c3d4', 55000)
    self.assertEqual('https://ci.chromium.org/p/chromium/builds/10000',
                     target.build_url)
