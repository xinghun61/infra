# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import os
import shutil
import sys

from infra.libs import git2
from infra.libs.git2.test import test_util


class TestRepo(test_util.TestBasis):
  def testEmptyRepo(self):
    r = git2.Repo('doesnt_exist')
    r.repos_dir = self.repos_dir

    with self.assertRaises(git2.CalledProcessError):
      self.capture_stdio(r.reify)

    with self.assertRaises(AssertionError):
      r.run('show-ref')

  def testDefaultRepo(self):
    r = self.mkRepo()
    r.reify()  # covers 'already initialized' portion of reify()
    self.assertEqual(r.run('rev-parse', 'branch_F').strip(), self.repo['F'])
    _, err = self.capture_stdio(r.run, 'rev-parse', 'rtaitnariostnr',
                                ok_ret={128})
    self.assertIn('fatal', err)

  def testDefaultRepoGit(self):
    shutil.move(self.repo.repo_path, self.repo.repo_path + '.git')
    self.repo.repo_path += '.git'
    r = self.mkRepo()
    self.assertFalse(r._repo_path.endswith('.git'))  # pylint: disable=W0212
    self.assertIn('refs/heads/branch_F', r.run('show-ref'))

  def testRefglob(self):
    r = self.mkRepo()
    self.assertEqual(
        {rf.ref for rf in r.refglob('*branch_*')},
        {'refs/heads/branch_'+l for l in 'FOKSZ'})
    self.assertIs(next(r.refglob('*branch_O')).repo, r)
    self.assertEqual(list(r.refglob('*atritaosrtientsaroitna*')), [])

  def testDryRun(self):
    r = self.mkRepo()
    r.dry_run = True
    self.assertIsNone(r.run('push', 'origin', 'HEAD'))

  def testRunIndata(self):
    r = self.mkRepo()
    with self.assertRaises(AssertionError):
      r.run('bogus', indata='spam', stdin=sys.stdin)
    self.assertEqual(
        r.run('rev-list', '--stdin', indata='branch_O~').splitlines()[0],
        self.repo['N'])

  def testGetCommit(self):
    # pylint: disable=W0212
    r = self.mkRepo()
    c = r.get_commit(self.repo['L'])
    self.assertEqual(c.hsh, self.repo['L'])
    self.assertEqual([self.repo['L']], r._commit_cache.keys())

    c2 = r.get_commit(self.repo['L'])
    self.assertIs(c, c2)

  def testGetCommitEviction(self):
    # pylint: disable=W0212
    r = self.mkRepo()
    r.MAX_CACHE_SIZE = 2
    L = r.get_commit(self.repo['L'])
    self.assertIs(L, r.get_commit(self.repo['L']))
    self.assertEqual(len(r._commit_cache), 1)

    O = r.get_commit(self.repo['O'])
    self.assertIs(L, r.get_commit(self.repo['L']))
    self.assertIs(O, r.get_commit(self.repo['O']))
    self.assertEqual(len(r._commit_cache), 2)

    N = r.get_commit(self.repo['N'])
    self.assertIs(N, r.get_commit(self.repo['N']))
    self.assertIs(O, r.get_commit(self.repo['O']))
    self.assertEqual(len(r._commit_cache), 2)

    self.assertIsNot(L, r.get_commit(self.repo['L']))

  def testIntern(self):
    r = self.mkRepo()
    hsh = r.intern('catfood')
    self.assertEqual(hsh, hashlib.sha1('blob 7\0catfood').hexdigest())
    self.assertEqual('catfood', r.run('cat-file', 'blob', hsh))

  def testGetRef(self):
    r = self.mkRepo()
    self.assertEqual(r['refs/heads/branch_Z'].commit.hsh,
                     'cd2277651786a3f5a8cefb6be22ab42988f25cd9')

  def testNonFastForward(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    D = r.get_commit(self.repo['D'])
    with self.assertRaises(git2.CalledProcessError):
      r.fast_forward_push({O: D})
    self.assertEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['O'])

  def testFastForward(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    S = r.get_commit(self.repo['S'])
    self.capture_stdio(r.fast_forward_push, {O: S})
    self.assertEqual(O.commit.hsh, self.repo['S'])
    self.assertEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['S'])

  def testEmptyFastForward(self):
    r = self.mkRepo()
    out, err = self.capture_stdio(r.fast_forward_push, {})
    self.assertEqual(out, '')
    self.assertEqual(err, '')

  def testShareObjectsFrom(self):
    r = self.mkRepo()
    # make a mirror of THAT
    r2 = git2.Repo('file://' + r.repo_path)
    r2.repos_dir = os.path.join(self.repos_dir, 'repos')
    self.capture_stdio(r2.reify, share_from=r)

    data = 'super-cool-blob'
    hsh = r.intern(data)
    self.assertEqual(r2.run('cat-file', 'blob', hsh), data)

  def testShareObjectsAdd(self):
    r = self.mkRepo()
    data = 'super-cool-blob'
    hsh = r.intern(data)
    # make a mirror of THAT
    r2 = git2.Repo('file://' + r.repo_path)
    r2.repos_dir = os.path.join(self.repos_dir, 'repos')
    self.capture_stdio(r2.reify)

    # blob is not there because it's a clone, but the blob wasn't in a commit
    with self.assertRaises(git2.CalledProcessError):
      r2.run('cat-file', 'blob', hsh)

    self.capture_stdio(r2.reify, share_from=r)
    self.assertEqual(r2.run('cat-file', 'blob', hsh), data)

    # reifying a second time shouldn't change the alternates file
    with open(os.path.join(r2.repo_path, 'objects', 'info', 'alternates')) as f:
      altfile = f.read()
    self.capture_stdio(r2.reify, share_from=r)
    with open(os.path.join(r2.repo_path, 'objects', 'info', 'alternates')) as f:
      self.assertEqual(altfile, f.read())

  def testShareObjectsStringPath(self):
    r = self.mkRepo()
    data = 'super-cool-blob'
    hsh = r.intern(data)
    # make a mirror of THAT
    r2 = git2.Repo('file://' + r.repo_path)
    r2.repos_dir = os.path.join(self.repos_dir, 'repos')
    self.capture_stdio(r2.reify)

    # blob is not there because it's a clone, but the blob wasn't in a commit
    with self.assertRaises(git2.CalledProcessError):
      r2.run('cat-file', 'blob', hsh)

    self.capture_stdio(r2.reify, share_from=r.repo_path)
    self.assertEqual(r2.run('cat-file', 'blob', hsh), data)

  def testFetch(self):
    r = self.mkRepo()
    br_O = self.repo.git('rev-parse', 'branch_O')[1].strip()
    br_O_ref = r['refs/heads/branch_O']

    with open(os.path.join(self.repo.repo_path, 'catfood'), 'w') as f:
      print >> f, 'It\'s cat food'
    self.repo.git('checkout', 'branch_O')
    self.repo.git('add', 'catfood')
    self.repo.git_commit('CF')
    new = self.repo.git('rev-parse', 'HEAD')[1].strip()
    self.assertEqual(br_O_ref.commit.hsh, br_O)
    self.capture_stdio(r.fetch)
    self.assertEqual(br_O_ref.commit.hsh, new)

  def testQueuedNonFastForward(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    D = r.get_commit(self.repo['D'])
    with self.assertRaises(git2.CalledProcessError):
      r.queue_fast_forward({O: D})
    self.assertEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['O'])

  def testQueuedFastForward(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    S = r.get_commit(self.repo['S'])
    self.capture_stdio(r.queue_fast_forward, {O: S})
    self.assertEqual(O.commit.hsh, self.repo['S'])
    self.assertNotEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['S'])
    self.capture_stdio(r.push_queued_fast_forwards)
    self.assertEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['S'])

  def testEmptyQueuedFastForward(self):
    r = self.mkRepo()
    out, err = self.capture_stdio(r.queue_fast_forward, {})
    self.assertEqual(out, '')
    self.assertEqual(err, '')
