# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap
import unittest

from infra.libs.deps2submodules import deps2submodules
from infra.libs.git2 import EMPTY_TREE
from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import TestRepo

import mock


def _pretty_print(internal_result):
  return (internal_result[0].splitlines(), internal_result[1])

class Deps2SubmodulesTest(unittest.TestCase):
  def testExcludeByPathPrefix(self):
    # https://stackoverflow.com/a/1412728/98761 discusses textwrap.dedent()
    #
    deps_file_content = textwrap.dedent("""\
        deps = {
          "abc/def": "https://chromium.googlesource.com/xyz/foo@5d0be3947e7e238f38516eddbe286a61d3ec4bc9",
          "fount/foo": "https://chromium.googlesource.com/xyz/bar@10803d79ece6d8752be370163d342030a816cb8f",
        }
        """)
    cut = deps2submodules.Deps2Submodules(deps_file_content, None, 'fount/')
    cut.Evaluate()
    return _pretty_print(cut._gitmodules)

  def testPruneConflict(self):
    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/quux": "https://chromium.googlesource.com/xyz/abc@db1a5a09f7ddd42f3ce395a761725516593fc4ff",
          "fount/quux/conflict": "https://chromium.googlesource.com/xyz/def@00e6690f83a9260717b1d38ce9b9332d6986516d",

          "fount/foo/bar": "https://chromium.googlesource.com/xyz/pqr@41d25f51c301c5eee3737998b0d86573e4e91b90",
          "fount/foo/bar/baz": "https://chromium.googlesource.com/xyz/ghi@dc030e592c36bfffe129fe0d3af4fb30dde35704",
        }
        """)
    cut = deps2submodules.Deps2Submodules(deps_file_content, None, 'fount/')
    cut.Evaluate()
    return _pretty_print(cut._gitmodules)

  def testElidedDeps(self):
    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/quux": None,

          "fount/foo/bar": {
            'url': "https://chromium.googlesource.com/xyz/abc@41d25f51c301c5eee3737998b0d86573e4e91b90",
          },
          "fount/foo/baz": {
            'url': "https://chromium.googlesource.com/xyz/pqr@1c9064284a24b3486015eafdb391b141c27ada2b",
            'condition': 'checkout_google_internal'
          },
        }
        """)
    cut = deps2submodules.Deps2Submodules(deps_file_content, None, 'fount/')
    cut.Evaluate()
    return _pretty_print(cut._gitmodules)

  def testSymbolicRef(self):
    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/one": "https://chromium.googlesource.com/xyz/abc@refs/heads/rogue",
          "fount/another": "https://chromium.googlesource.com/xyz/def",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, url, ref):
        if (url, ref) == ('https://chromium.googlesource.com/xyz/def',
                          'master'):
          return '2a2337d1d2e5bfffa670a91f2231d5c428dfaadd'
        elif (url, ref) == ('https://chromium.googlesource.com/xyz/pqr',
                            'master'):
          return 'a0cde59caf0889feb56aac1abd6eb5732ff0ddb8'
        else:
          assert (url, ref) == ('https://chromium.googlesource.com/xyz/abc',
                                'refs/heads/rogue')
          return 'cc103db39df46ec8fdce463279180d948ff6e81e'

    cut = deps2submodules.Deps2Submodules(deps_file_content,
                                          FakeResolver(), 'fount/')
    cut.Evaluate()
    first_result = _pretty_print(cut._gitmodules)

    new_deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/one": "https://chromium.googlesource.com/xyz/abc@refs/heads/rogue",
          "fount/another": "https://chromium.googlesource.com/xyz/def",
          "fount/yet/another": "https://chromium.googlesource.com/xyz/pqr@origin/master",
        }
        """)
    cut = cut.withUpdatedDeps(new_deps_file_content)
    cut.Evaluate()
    second_result = _pretty_print(cut._gitmodules)
    return (first_result,second_result)

  def testExtraSubmodules(self):
    deps_file_content = textwrap.dedent("""\
        deps = {
          "abc/def": "https://chromium.googlesource.com/xyz/foo@5d0be3947e7e238f38516eddbe286a61d3ec4bc9",
          "fount/foo": "https://chromium.googlesource.com/xyz/bar@10803d79ece6d8752be370163d342030a816cb8f",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, url, ref):
        assert (url, ref) == (
            'https://chromium.googlesource.com/chromium/src/out',
            'refs/heads/master')
        return 'e5e08ac07d8a3530de282fbf99472c4c7625f949'
    cut = deps2submodules.Deps2Submodules(deps_file_content, FakeResolver(),
        'fount/',
        ['fount/out=https://chromium.googlesource.com/chromium/src/out'])
    cut.Evaluate()
    return _pretty_print(cut._gitmodules)

  def testMissingSymbolicRef(self):
    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/one": "https://chromium.googlesource.com/xyz/abc@refs/heads/rogue",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, _url, _ref):
        return None
    cut = deps2submodules.Deps2Submodules(deps_file_content,
                                          FakeResolver(), 'fount/')
    with self.assertRaises(Exception):
      cut.Evaluate()

  def testGitRefResolver(self):
    clock = TestClock()
    dep = TestRepo('dep', clock)
    dep['refs/heads/master'].make_commit('first', {'README':'hello, world'})

    local = TestRepo('local', clock)

    resolver = deps2submodules.GitRefResolver(local)
    url = dep.repo_path
    result1 = resolver.Resolve(url, 'refs/heads/master')
    result2 = resolver.Resolve(url, 'no/such/ref')
    return (result1, result2)

  def testUpdateSubmodules(self):
    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/a": "https://example.com/xyz/a@deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
          "fount/b": "https://example.com/xyz/b@cafebabecafebabecafebabecafebabecafebabe",
        }
        """)
    cut = deps2submodules.Deps2Submodules(deps_file_content, None, 'fount/')
    cut.Evaluate()

    repo = TestRepo('repo', TestClock())

    hsh = cut.UpdateSubmodules(repo, EMPTY_TREE)
    tree_dump = repo.run('ls-tree', '-r', hsh)
    file_dump = repo.run('cat-file', '-p', '%s:.gitmodules' % hsh)
    return (file_dump, tree_dump)

  @mock.patch('requests.get')
  def testAbbreviatedCommitHash(self, mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = textwrap.dedent("""\
        )]}'
        {
           "commit": "deadbabefacebeeffacefeedbeefabcdeffedcba",
           "other": "irrelevant stuff"
        }
        """)
    mock_get.side_effect = [mock_response]

    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/a": "https://example.com/xyz/a@deadbabe",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, _url, _ref):
        return None
    cut = deps2submodules.Deps2Submodules(deps_file_content,
                                          FakeResolver(), 'fount/')
    cut.Evaluate()
    self.assertEqual(mock_get.call_count, 1)
    return _pretty_print(cut._gitmodules)

  @mock.patch('requests.get')
  def testAbbreviatedCommitHash_missingHeader(self, mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = textwrap.dedent("""\
        {
           "commit": "deadbabefacebeeffacefeedbeefabcdeffedcba",
           "other": "irrelevant stuff"
        }
        """)
    mock_get.side_effect = [mock_response]

    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/a": "https://example.com/xyz/a@deadbabe",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, _url, _ref):
        return None
    cut = deps2submodules.Deps2Submodules(deps_file_content,
                                          FakeResolver(), 'fount/')
    with self.assertRaises(Exception):
      cut.Evaluate()

  @mock.patch('requests.get')
  def testAbbreviatedCommitHash_missingField(self, mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = textwrap.dedent("""\
        )]}'
        {
           "kommit": "deadbabefacebeeffacefeedbeefabcdeffedcba",
           "other": "irrelevant stuff"
        }
        """)
    mock_get.side_effect = [mock_response]

    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/a": "https://example.com/xyz/a@deadbabe",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, _url, _ref):
        return None
    cut = deps2submodules.Deps2Submodules(deps_file_content,
                                          FakeResolver(), 'fount/')
    with self.assertRaises(Exception):
      cut.Evaluate()

  @mock.patch('requests.get')
  def testAbbreviatedCommitHash_badStatus(self, mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.text = 'Something went wrong.'
    mock_get.side_effect = [mock_response]

    deps_file_content = textwrap.dedent("""\
        deps = {
          "fount/a": "https://example.com/xyz/a@deadbabe",
        }
        """)
    class FakeResolver(object):
      def Resolve(self, _url, _ref):
        return None
    cut = deps2submodules.Deps2Submodules(deps_file_content,
                                          FakeResolver(), 'fount/')
    with self.assertRaises(Exception):
      cut.Evaluate()
