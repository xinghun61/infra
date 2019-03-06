# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.testcase import TestCase

from model.isolated_target import IsolatedTarget


class IsolatedTargetTest(TestCase):

  def setUp(self):
    super(IsolatedTargetTest, self).setUp()
    for pos in range(100):
      commit_position = 55000 + pos * 13
      entry = IsolatedTarget.Create(
          843400990909000 + pos, 'chromium', 'ci', 'chromium.linux',
          'Linux Builder', 'chromium.googlesource.com', 'chromium/src',
          'refs/heads/master', '', 'browser_tests', 'abcdef%dabcdef' % pos,
          commit_position, '%d' % commit_position)
      entry.put()

  def testFindIsolate(self):
    before = IsolatedTarget.FindIsolateBeforeCommitPositionByBucket(
        'chromium', 'ci', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(before[0],
                     IsolatedTarget.get_by_id('843400990909049/browser_tests'))
    at = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByBucket(
        'chromium', 'ci', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(at[0],
                     IsolatedTarget.get_by_id('843400990909050/browser_tests'))
    after = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByBucket(
        'chromium', 'ci', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55655)
    self.assertEqual(after[0],
                     IsolatedTarget.get_by_id('843400990909051/browser_tests'))

  def testFindIsolateByMaster(self):
    before = IsolatedTarget.FindIsolateBeforeCommitPositionByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(before[0],
                     IsolatedTarget.get_by_id('843400990909049/browser_tests'))
    at = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55650)
    self.assertEqual(at[0],
                     IsolatedTarget.get_by_id('843400990909050/browser_tests'))
    after = IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests', 55655)
    self.assertEqual(after[0],
                     IsolatedTarget.get_by_id('843400990909051/browser_tests'))
    latest = IsolatedTarget.FindLatestIsolateByMaster(
        'chromium.linux', 'Linux Builder', 'chromium.googlesource.com',
        'chromium/src', 'refs/heads/master', 'browser_tests')
    self.assertEqual(latest[0],
                     IsolatedTarget.get_by_id('843400990909099/browser_tests'))

  def testIsolatedHash(self):
    isolated_hash = 'isolated_hash'
    target = IsolatedTarget.Create(
        10000, 'chromium', 'ci', 'chromium.linux', 'Linux Builder',
        'chromium.googlesource.com', 'chromium/src', 'refs/heads/master', '',
        'browser_tests', isolated_hash, 55000, '55000')
    self.assertEqual(isolated_hash, target.GetIsolatedHash())

  def testBuildUrl(self):
    build_id = 10000
    target = IsolatedTarget.Create(build_id, 'chromium', 'ci', 'chromium.linux',
                                   'Linux Builder', 'chromium.googlesource.com',
                                   'chromium/src', 'refs/heads/master', '',
                                   'browser_tests', 'a1b2c3d4', 55000, '55000')
    self.assertEqual('https://ci.chromium.org/b/10000', target.build_url)
