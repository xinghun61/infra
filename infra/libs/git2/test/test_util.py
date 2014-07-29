# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import sys
import tempfile

import testing_support

from infra.libs import git2


class TestBasis(testing_support.git.unittest_helpers.GitRepoReadWriteTestBase):
  # TODO(iannucci): Make this covered by the other tests in this folder

  REPO_SCHEMA = """
  A B C D E F
        D L M N O
                O P Q R S
    B G H I J K
        H         Z
                O Z
  """

  @staticmethod
  def capture_stdio(fn, *args, **kwargs):  # pragma: no cover
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

  def setUp(self):  # pragma: no cover
    # "super on old-style class" pylint: disable=E1002
    self.repos_dir = tempfile.mkdtemp(suffix='.git_test')
    super(TestBasis, self).setUp()
    self.repo.git('branch', 'branch_O', self.repo['O'])

  def tearDown(self):  # pragma: no cover
    # "super on old-style class" pylint: disable=E1002
    shutil.rmtree(self.repos_dir)
    super(TestBasis, self).tearDown()

  def mkRepo(self): # pragma: no cover
    r = git2.Repo(self.repo.repo_path)
    r.repos_dir = os.path.join(self.repos_dir, 'repos')
    self.capture_stdio(r.reify)
    return r
