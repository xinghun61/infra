# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra.libs import git2
from infra.libs.git2.test import test_util


class TestRef(test_util.TestBasis):
  COMMIT_D = {"path/cool_file": {"data": "useless content!"}}
  COMMIT_M = {"path/cool_file": {"data": "super neat content!"}}
  COMMIT_O = {"path/cool_file": {"data": "super neat content!"}}

  def testComparison(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    self.assertEqual(O, O)
    self.assertEqual(O, r['refs/heads/branch_O'])

    N = r['refs/heads/branch_K']
    self.assertNotEqual(O, N)

  def testRepr(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    self.assertEqual("Ref(%r, 'refs/heads/branch_O')" % r, repr(O))

  def testCommit(self):
    r = self.mkRepo()
    self.assertEqual(
        r['refs/heads/branch_O'].commit.hsh,
        self.repo['O'])

  def testCommitBogus(self):
    r = self.mkRepo()
    self.assertIs(r['refs/heads/bogus'].commit, git2.INVALID)
    # exercise __ne__ and __eq__
    self.assertNotEqual(r['refs/heads/bogus'].commit,
                        r['refs/heads/other_bogus'].commit)
    self.assertFalse(r['refs/heads/bogus'].commit ==
                     r['refs/heads/other_bogus'].commit)

  def testTo(self):
    r = self.mkRepo()
    A = r['refs/heads/root_A']
    O = r['refs/heads/branch_O']
    self.assertEqual(
        list(c.hsh for c in A.to(O)),
        [self.repo[c] for c in 'BCDLMNO']
    )

  def testToSubpath(self):
    r = self.mkRepo()
    A = r['refs/heads/root_A']
    O = r['refs/heads/branch_O']
    # See the COMMIT_* class variables for commit content.
    # M and O have the same content for cool_file, so it won't show up here.
    self.assertEqual(
        list(c.hsh for c in A.to(O, 'path')),
        [self.repo[c] for c in 'DM']
    )

  def testInvalidTo(self):
    r = self.mkRepo()
    dne = r['refs/heads/doesnt_exist_yet']
    inv = r[git2.INVALID]
    O = r['refs/heads/branch_O']
    self.assertIs(dne.commit, git2.INVALID)
    self.assertIs(inv.commit, git2.INVALID)
    self.assertEqual(
        list(c.hsh for c in dne.to(O)),
        [self.repo[c] for c in 'ABCDLMNO']
    )
    self.assertEqual(
        list(c.hsh for c in inv.to(O)),
        [self.repo[c] for c in 'ABCDLMNO']
    )

  def testFastForward(self):
    r = self.mkRepo()
    O = r['refs/heads/branch_O']
    S = r.get_commit(self.repo['S'])
    self.capture_stdio(O.fast_forward, S)
    self.assertEqual(O.commit.hsh, self.repo['S'])

  def testFastForwardINVALID(self):
    r = self.mkRepo()
    O = r['refs/heads/watville']
    self.assertIs(O.commit, git2.INVALID)
    S = r.get_commit(self.repo['S'])
    self.capture_stdio(O.fast_forward, S)
    self.assertEqual(O.commit.hsh, self.repo['S'])

  def testUpdateTo(self):
    r = self.mkRepo()
    S = r['refs/heads/branch_S']
    O = r.get_commit(self.repo['O'])
    with self.assertRaises(git2.CalledProcessError):
      self.capture_stdio(S.fast_forward, O)
    self.capture_stdio(S.update_to, O)
    self.assertEqual(S.commit.hsh, self.repo['O'])

  def testHash(self):
    # ensure that Ref's can be used as keys in a dict
    r = self.mkRepo()
    mapping = {}
    mapping[r['refs/heads/branch_O']] = True
    mapping[r['refs/heads/branch_O']] = True
    self.assertEqual(len(mapping), 1)
