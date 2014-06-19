# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import shutil
import sys
import tempfile

# 'super on old-style class' - pylint: disable=E1002
# 'cannot import' - pylint: disable=F0401
# 'no __init__ method' - pylint: disable=W0232
from testing_support import git_test_utils

from infra.services.gnumbd.support import git, util

class TestBasis(git_test_utils.GitRepoReadWriteTestBase):
  REPO_SCHEMA = """
  A B C D E F
        D L M N O
                O P Q R S
    B G H I J K
        H         Z
                O Z
  """

  @staticmethod
  def capture_stdio(fn, *args, **kwargs):
    stdout = sys.stdout
    stderr = sys.stderr
    try:
      # "multiple statements on a line" pylint: disable=C0321
      with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        sys.stdout = out
        sys.stderr = err
        fn(*args, **kwargs)
        out.seek(0)
        err.seek(0)
        return out.read(), err.read()
    finally:
      sys.stdout = stdout
      sys.stderr = stderr

  def setUp(self):
    self.repos_dir = tempfile.mkdtemp(suffix='.gnumbd')
    super(TestBasis, self).setUp()
    self.repo.git('branch', 'branch_O', self.repo['O'])

  def tearDown(self):
    shutil.rmtree(self.repos_dir)
    super(TestBasis, self).tearDown()

  def mkRepo(self):
    r = git.Repo(self.repo.repo_path)
    r.repos_dir = self.repos_dir
    self.capture_stdio(r.reify)
    return r


class TestRepo(TestBasis):
  def testEmptyRepo(self):
    r = git.Repo('doesnt_exist')
    r.repos_dir = self.repos_dir

    with self.assertRaises(util.CalledProcessError):
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


class TestRef(TestBasis):
  def testComparison(self):
    r = self.mkRepo()
    O = git.Ref(r, 'refs/heads/branch_O')
    self.assertEqual(O, O)
    self.assertEqual(O, git.Ref(r, 'refs/heads/branch_O'))

    N = git.Ref(r, 'refs/heads/branch_K')
    self.assertNotEqual(O, N)

  def testRepr(self):
    r = self.mkRepo()
    O = git.Ref(r, 'refs/heads/branch_O')
    self.assertEqual("Ref(%r, 'refs/heads/branch_O')" % r, repr(O))

  def testCommit(self):
    r = self.mkRepo()
    self.assertEqual(
        git.Ref(r, 'refs/heads/branch_O').commit.hsh,
        self.repo['O'])

  def testCommitBogus(self):
    r = self.mkRepo()
    self.assertIs(git.Ref(r, 'refs/heads/bogus').commit, git.INVALID)
    # exercise __ne__ and __eq__
    self.assertNotEqual(git.Ref(r, 'refs/heads/bogus').commit,
                        git.Ref(r, 'refs/heads/other_bogus').commit)
    self.assertFalse(git.Ref(r, 'refs/heads/bogus').commit ==
                     git.Ref(r, 'refs/heads/other_bogus').commit)

  def testTo(self):
    r = self.mkRepo()
    A = git.Ref(r, 'refs/heads/root_A')
    O = git.Ref(r, 'refs/heads/branch_O')
    self.assertEqual(
        list(c.hsh for c in A.to(O)),
        [self.repo[c] for c in 'BCDLMNO']
    )

  def testNonFastForward(self):
    r = self.mkRepo()
    O = git.Ref(r, 'refs/heads/branch_O')
    D = r.get_commit(self.repo['D'])
    with self.assertRaises(git.CalledProcessError):
      O.fast_forward_push(D)
    self.assertEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['O'])

  def testFastForward(self):
    r = self.mkRepo()
    O = git.Ref(r, 'refs/heads/branch_O')
    S = r.get_commit(self.repo['S'])
    self.capture_stdio(O.fast_forward_push, S)
    self.assertEqual(O.commit.hsh, self.repo['S'])
    self.assertEqual(
        self.repo.git('rev-parse', 'branch_O').stdout.strip(),
        self.repo['S'])


class TestCommit(TestBasis):
  def testComparison(self):
    r = self.mkRepo()
    c = git.Ref(r, 'refs/heads/branch_O').commit
    self.assertEqual(c, c)
    self.assertEqual(c, git.Ref(r, 'refs/heads/branch_O').commit)
    self.assertNotEqual(c, git.Ref(r, 'refs/heads/branch_S').commit)
    self.assertIs(c.repo, r)

  def testRepr(self):
    r = self.mkRepo()
    c = git.Ref(r, 'refs/heads/branch_O').commit
    self.assertEqual("Commit(%r, %r)" % (r, self.repo['O']), repr(c))

  def testData(self):
    r = self.mkRepo()
    d = git.Ref(r, 'refs/heads/branch_O').commit.data
    self.assertEqual(d.committer.email, 'commitish@example.com')

  def testBogus(self):
    r = self.mkRepo()
    d = git.Commit(r, 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef').data
    self.assertIs(d, git.INVALID)
    self.assertIs(d.committer, git.INVALID)
    self.assertIs(d.committer.alter(user='tom'), git.INVALID)

  def testParent(self):
    r = self.mkRepo()
    c = git.Ref(r, 'refs/heads/branch_O').commit
    self.assertEqual(c.parent.hsh, self.repo['N'])

    a = git.Ref(r, 'refs/heads/root_A').commit
    self.assertIsNone(a.parent)

    z = git.Ref(r, 'refs/heads/branch_Z').commit
    self.assertIs(z.parent, git.INVALID)

  def testAlter(self):
    r = self.mkRepo()
    c = git.Ref(r, 'refs/heads/branch_O').commit
    d = c.data

    a = c.alter(committer=d.committer.alter(email='bob@dude.example.com'))
    self.assertEqual(a.hsh, 'fadfbe63d40f60f5313a71a1c9d72a741ee91770')

    with self.assertRaises(Exception):
      c.alter(tree='failbeef')

