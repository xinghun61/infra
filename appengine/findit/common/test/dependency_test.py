# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.dependency import Dependency


class DependencyTest(unittest.TestCase):
  def testParentChild(self):
    parent = Dependency(
        'a/', 'https://cr.googlesource.com/cr/a.git', '12a', 'DEPS')
    child = Dependency(
        'a/b/', 'https://cr.googlesource.com/cr/b.git', '12b', 'DEPS')

    child.SetParent(parent)
    self.assertTrue(child.parent == parent)
    self.assertIn(child.path, parent.children)
    self.assertTrue(child == parent.children[child.path])

  def testToDict(self):
    root_dep = Dependency(
        'a/', 'https://cr.googlesource.com/cr/a.git', '12a', 'DEPS')
    sub_dep = Dependency(
        'a/b/', 'https://cr.googlesource.com/cr/b.git', '12b', 'DEPS')
    expected_dep_tree_json = {
        'path': 'a/',
        'repo_url': 'https://cr.googlesource.com/cr/a.git',
        'revision': '12a',
        'deps_file': 'DEPS',
        'children': {
            'a/b/': {
              'path': 'a/b/',
              'repo_url': 'https://cr.googlesource.com/cr/b.git',
              'revision': '12b',
              'deps_file': 'DEPS',
              'children': {
              }
            }
        }
    }

    sub_dep.SetParent(root_dep)
    self.assertEqual(expected_dep_tree_json, root_dep.ToDict())
