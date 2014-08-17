# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict as OD

from infra.libs import git2
from infra.libs.git2.test import test_util
from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import GitFile
from infra.libs.git2.testing_support import TestRepo


class TestTestRepo(test_util.TestBasis):
  def testEmptyRepo(self):
    r = TestRepo('foo', TestClock())
    with self.assertRaises(git2.CalledProcessError):
      list(r.refglob('*'))  # no refs yet
    self.assertIsNotNone(r.repo_path)
    ref = r['refs/heads/master']
    ref.synthesize_commit('Initial Commit')
    self.assertEqual(list(r.refglob('*')), [ref])

  def testInitialCommit(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    ref.synthesize_commit('Initial Commit', {
      'cool_file': 'whazzap',
      'subdir': {
        'crazy times': 'this is awesome'
      }
    })
    self.assertEqual(list(r.refglob('*')), [ref])
    self.assertEqual(r.snap(include_committer=True), {
      'refs/heads/master': OD([
        ('b7c705ceddb223c09416b78e87dc8c41e7035a36', [
          # 'line too long' pylint: disable=C0301
          'committer Test User <test_user@example.com> 2014-06-13 00:09:06 +0800',
          '',
          'Initial Commit'
        ])
      ])
    })
    self.assertEqual('whazzap', r.run('cat-file', 'blob', 'master:cool_file'))
    self.assertEqual('this is awesome',
                     r.run('cat-file', 'blob', 'master:subdir/crazy times'))

  def testMultiCommit(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    ref.synthesize_commit('Initial Commit', {
      'cool_file': 'whazzap',
      'subdir': {
        'crazy times': 'this is awesome'
      }
    })
    ref.synthesize_commit('Second commit')
    self.assertEqual(r.snap(), {
      'refs/heads/master': OD([
        ('86fa6839ec4bb328e82bde851ad131c01b10162d', ['Second commit']),
        ('b7c705ceddb223c09416b78e87dc8c41e7035a36', ['Initial Commit'])
      ])
    })
    # second commit had the default tree
    self.assertEqual('contents', r.run('cat-file', 'blob', 'master:file'))
    self.assertEqual('this is awesome',
                     r.run('cat-file', 'blob', 'master~:subdir/crazy times'))


  def testSpec(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    ref.synthesize_commit('Initial Commit', {
      'cool_file': ('whazzap', 0755),  # executable
      'subdir': {
        'crazy times': GitFile('this is awesome')  # explicit entry
      }
    })
    self.assertEqual(r.snap(), {
      'refs/heads/master': OD([
        ('29c7b88f7eeed928d38c692052bd0a26f7899864', ['Initial Commit'])
      ])
    })
    self.assertEqual('whazzap', r.run('cat-file', 'blob', 'master:cool_file'))
    self.assertEqual('this is awesome',
                     r.run('cat-file', 'blob', 'master:subdir/crazy times'))
    with self.assertRaises(AssertionError):
      ref.synthesize_commit('invalid object', {'not', 'a', 'spec'})


  def testConfigRefOmission(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    ref.synthesize_commit('Initial Commit', {
      'cool_file': ('whazzap', 0755),  # executable
      'subdir': {
        'crazy times': GitFile('this is awesome')  # explicit entry
      }
    })
    cref = r['refs/fancy-config/main']
    cref.synthesize_commit('Config data', {'config.json': '{"hello": "world"}'})
    self.assertEqual(r.snap(), {
      'refs/heads/master': OD([
        ('29c7b88f7eeed928d38c692052bd0a26f7899864', ['Initial Commit'])
      ])
    })
    self.assertEqual(r.snap(include_config=True), {
      'refs/heads/master': OD([
        ('29c7b88f7eeed928d38c692052bd0a26f7899864', ['Initial Commit'])
      ]),
      'refs/fancy-config/main': OD([
        ('ba5d4a2b2604ec58de362ec8df17b7797a142be2', ['Config data'])
      ])
    })

  def testRepoMirrorOf(self):
    r = TestRepo('local', TestClock())
    m = TestRepo('mirror', TestClock(), mirror_of=r.repo_path)
    self.capture_stdio(m.reify)
    ref = r['refs/heads/master']
    ref.synthesize_commit('Initial Commit')
    self.assertEqual(list(r.refglob('*')), [ref])
    with self.assertRaises(git2.CalledProcessError):
      list(m.refglob('*'))  # no refs yet in mirror
    self.capture_stdio(m.run, 'fetch')
    self.assertEqual(list(m.refglob('*')), [m['refs/heads/master']])
    self.assertEqual(r.snap(), m.snap())