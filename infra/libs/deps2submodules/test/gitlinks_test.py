# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.libs.deps2submodules import deps2submodules
from infra.libs.deps2submodules import gitlinks
from infra.libs.git2.testing_support import GitFile
from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import TestRepo


SubmodData = deps2submodules.SubmodData


# The SHA-1 hash values in this test are all just arbitrary gibberish.
class GitlinksTest(unittest.TestCase):
  def testItAll(self):
    clock = TestClock()
    repo = TestRepo('repo', clock)

    content = {
        'abc': {'file1': 'hello, world'},
        'ghi': {
          'zyx': {'file2': 'good-bye, whirled'}
        }
    }

    commit1 = repo['refs/heads/master'].make_commit('first', content)

    def _arbitrary_submod_data(hsh):
      return SubmodData(revision=hsh, url='unused')

    submods = {
        'abc/pqr/wow': _arbitrary_submod_data(
            'f719efd430d52bcfc8566a43b2eb655688d38871'),
        'ghi/aaa': _arbitrary_submod_data(
            'f719efd430d52bcfc8566a43b2eb655688d38871'),
        'abc/trl': _arbitrary_submod_data(
            '2bdf67abb163a4ffb2d7f3f0880c9fe5068ce782'),
        'abc/def': _arbitrary_submod_data(
            '8510665149157c2bc901848c3e0b746954e9cbd9'),
        'ghi/zyx/deep': _arbitrary_submod_data(
            '54f9d6da5c91d556e6b54340b1327573073030af'),
        'abc/xyz': _arbitrary_submod_data(
            'fe7900bcbd294970da3296db5cf2020b4391a639')
    }

    gitmodules = GitFile('ignored, so it does not matter what I put here')
    result = gitlinks.Gitlinks(repo,
                               gitmodules.intern(repo),
                               submods,
                               commit1.data.tree).BuildRootTree()
    return repo.run('ls-tree', '-r', result).splitlines()
