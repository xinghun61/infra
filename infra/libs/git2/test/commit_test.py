# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import os

from infra.libs import git2
from infra.libs.git2.test import test_util

from infra_libs.infra_types import freeze


class TestCommit(test_util.TestBasis):
  def testComparison(self):
    r = self.mkRepo()
    c = r['refs/heads/branch_O'].commit
    self.assertEqual(c, c)
    self.assertEqual(c, r['refs/heads/branch_O'].commit)
    self.assertNotEqual(c, r['refs/heads/branch_S'].commit)
    self.assertIs(c.repo, r)

  def testRepr(self):
    r = self.mkRepo()
    c = r['refs/heads/branch_O'].commit
    self.assertEqual("Commit(%r, %r)" % (r, self.repo['O']), repr(c))

  def testData(self):
    r = self.mkRepo()
    d = r['refs/heads/branch_O'].commit.data
    self.assertEqual(d.committer.email, 'commitish@example.com')

  def testBogus(self):
    r = self.mkRepo()
    d = git2.Commit(r, 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef').data
    self.assertIs(d, git2.INVALID)
    self.assertIs(d.committer, git2.INVALID)
    self.assertIs(d.committer.alter(user='tom'), git2.INVALID)

  def testParent(self):
    r = self.mkRepo()
    c = r['refs/heads/branch_O'].commit
    self.assertEqual(c.parent.hsh, self.repo['N'])

    a = r['refs/heads/root_A'].commit
    self.assertIsNone(a.parent)

    z = r['refs/heads/branch_Z'].commit
    self.assertIs(z.parent, git2.INVALID)

  def testAlter(self):
    r = self.mkRepo()
    c = r['refs/heads/branch_O'].commit
    d = c.data

    a = c.alter(committer=d.committer.alter(email='bob@dude.example.com'))
    self.assertEqual(a.hsh, '03607bb224aea0bc0623918c59883be39a49dd6b')

    with self.assertRaises(Exception):
      c.alter(tree='failbeef')

  def testNotes(self):
    env = os.environ.copy()
    env.update(self.repo.get_git_commit_env())

    r = self.mkRepo()
    self.assertIsNone(r['refs/heads/branch_O'].commit.notes())
    r.run('notes', '--ref', 'refs/notes/wacko', 'add', 'refs/heads/branch_O',
          '-m', 'cool notes, fellow robot!', env=env)
    self.assertIsNone(r['refs/heads/branch_O'].commit.notes())
    self.assertEqual(r['refs/heads/branch_O'].commit.notes('refs/notes/wacko'),
                     # note the trailing \n
                     'cool notes, fellow robot!\n')

  def testExtraFooters(self):
    env = os.environ.copy()
    env.update(self.repo.get_git_commit_env())

    r = self.mkRepo()
    self.assertEqual(r['refs/heads/branch_O'].commit.extra_footers(), {})
    r.run('notes', '--ref', 'refs/notes/extra_footers', 'add',
          'refs/heads/branch_O', '-m', '\n'.join([
            'Happy-Footer: sup',
            'Nerd-Rage: extreme',
            'Happy-Footer: sup2',
          ]),
          env=env)
    self.assertEqual(
      r['refs/heads/branch_O'].commit.extra_footers(),
      freeze(collections.OrderedDict([
        ('Happy-Footer', ['sup', 'sup2']),
        ('Nerd-Rage', ['extreme']),
      ]))
    )
