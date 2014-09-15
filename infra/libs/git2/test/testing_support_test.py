# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict as OD

from infra.libs.git2.test import test_util
from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import GitFile
from infra.libs.git2.testing_support import TestRepo


class TestTestRepo(test_util.TestBasis):
  def testEmptyRepo(self):
    r = TestRepo('foo', TestClock())
    self.assertEqual(list(r.refglob()), [])
    self.assertIsNotNone(r.repo_path)
    self.assertEquals(r.short_name, 'foo')
    self.assertEqual(r.snap(), {})
    ref = r['refs/heads/master']
    ref.make_full_tree_commit('Initial Commit')
    self.assertEqual(list(r.refglob()), [ref])

  def testInitialCommit(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    ref.make_full_tree_commit('Initial Commit', {
      'cool_file': 'whazzap',
      'subdir': {
        'crazy times': 'this is awesome'
      }
    })
    self.assertEqual(list(r.refglob()), [ref])
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
    ref.make_full_tree_commit('Initial Commit', {
      'cool_file': 'whazzap',
      'subdir': {
        'crazy times': 'this is awesome'
      }
    })
    ref.make_full_tree_commit('Second commit')
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
    ref.make_full_tree_commit('Initial Commit', {
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
      ref.make_full_tree_commit('invalid object', {'not', 'a', 'spec'})


  def testConfigRefOmission(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    ref.make_full_tree_commit('Initial Commit', {
      'cool_file': ('whazzap', 0755),  # executable
      'subdir': {
        'crazy times': GitFile('this is awesome')  # explicit entry
      }
    })
    cref = r['refs/fancy-config/main']
    cref.make_full_tree_commit('Config data',
                               {'config.json': '{"hello": "world"}'})
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
    ref.make_full_tree_commit('Initial Commit')
    self.assertEqual(list(r.refglob()), [ref])
    self.assertEqual(list(m.refglob()), [])
    self.capture_stdio(m.run, 'fetch')
    self.assertEqual(list(m.refglob()), [m['refs/heads/master']])
    self.assertEqual(r.snap(), m.snap())

  def testSpecFor(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    spec = {
      'cool_file': ('whazzap', 0755),  # executable
      'subdir': {
        'crazy times': ('this is awesome', 0644)
      }
    }
    c = ref.make_full_tree_commit('Initial Commit', spec)
    self.assertEquals(spec, r.spec_for(c))

    # can take a raw tree hash too
    self.assertEquals(
      r.spec_for(r.run('rev-parse', '%s:subdir' % c.hsh).strip()), {
        'crazy times': ('this is awesome', 0644)
      }
    )

  def testMergeSpecs(self):
    r = TestRepo('foo', TestClock())
    ref = r['refs/heads/master']
    spec = {
      'cool_file': ('whazzap', 0755),  # executable
      'subdir': {
        'crazy times': ('this is awesome', 0644)
      },
      'nested': {
        'nested_file': 'one thing',
        'nested_carry': 'can\'t touch this',
      },
      'carry_over': 'this is the same before and after',
    }
    ref.make_commit('Initial Commit', spec)
    c = ref.make_commit('Differential Commit', {
      'cool_file': None,
      'subdir': 'now its a file',
      'nested': {
        'nested_file': 'other thing'
      },
      'other_dir': {
        'neat-o': 'it\'s a neat file!'
      },
    })
    self.assertEquals(r.spec_for(c), {
      'subdir': ('now its a file', 0644),
      'other_dir': {
        'neat-o': ('it\'s a neat file!', 0644)
      },
      'nested': {
        'nested_file': ('other thing', 0644),
        'nested_carry': ('can\'t touch this', 0644)
      },
      'carry_over': ('this is the same before and after', 0644),
    })
