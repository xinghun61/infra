# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import textwrap
import unittest

from infra.libs.deps import dependency
from infra.libs.deps import deps_parser


class DepsParserTest(unittest.TestCase):
  def testVarNotDefined(self):
    local_scope = {'vars': {}}
    var_impl = deps_parser.VarImpl(local_scope)
    self.assertRaisesRegexp(
        KeyError, 'Var is not defined: a', var_impl.Lookup, 'a')

  def testVarDefined(self):
    local_scope = {'vars': {'a': '1'}}
    var_impl = deps_parser.VarImpl(local_scope)
    self.assertEqual('1', var_impl.Lookup('a'))

  def testParseVars(self):
    result = deps_parser.ParseDEPSContent('', keys=['vars'])
    self.assertEqual(1, len(result))
    self.assertEqual({}, result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            vars = {
              'a': '1',
              'b': '2',
            }"""),
        keys=['vars'])
    expected_vars = {'a': '1', 'b': '2'}
    self.assertEqual(1, len(result))
    self.assertEqual(expected_vars, result[0])

  def testParseAllowedHosts(self):
    result = deps_parser.ParseDEPSContent('', keys=['allowed_hosts'])
    self.assertEqual(1, len(result))
    self.assertEqual([], result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            allowed_hosts = [
              'host1',
              'host2',
            ]"""),
        keys=['allowed_hosts'])
    expected_allowed_hosts = ['host1', 'host2']
    self.assertEqual(1, len(result))
    self.assertEqual(expected_allowed_hosts, result[0])

  def testParseDeps(self):
    result = deps_parser.ParseDEPSContent('', keys=['deps'])
    self.assertEqual(1, len(result))
    self.assertEqual({}, result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            vars = {
              'cr_repo': 'https://cr.repo',
              'a': '1',
            }
            deps = {
              'depA': Var('cr_repo') + '/a.git' + '@' + Var('a'),
            }"""),
        keys=['deps'])
    expected_deps = {
        'depA': 'https://cr.repo/a.git@1'
    }
    self.assertEqual(1, len(result))
    self.assertEqual(expected_deps, result[0])

  def testParseDepsOs(self):
    result = deps_parser.ParseDEPSContent('', keys=['deps_os'])
    self.assertEqual(1, len(result))
    self.assertEqual({}, result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            vars = {
              'cr_repo': 'https://cr.repo',
              'a': '1',
            }
            deps_os = {
              'win': {
                'depA': Var('cr_repo') + '/a.git' + '@' + Var('a'),
              },
              'unix': {
                'depA': None,
              }
            }"""),
        keys=['deps_os'])
    expected_deps_os = {
        'win': {
          'depA': 'https://cr.repo/a.git@1'
        },
        'unix': {
          'depA': None
        }
    }
    self.assertEqual(1, len(result))
    self.assertEqual(expected_deps_os, result[0])

  def testParseIncludeRules(self):
    result = deps_parser.ParseDEPSContent('', keys=['include_rules'])
    self.assertEqual(1, len(result))
    self.assertEqual([], result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            include_rules = [
              '+base',
            ]"""),
        keys=['include_rules'])
    expected_include_rules = ['+base']
    self.assertEqual(1, len(result))
    self.assertEqual(expected_include_rules, result[0])

  def testParseSkipChildIncludes(self):
    result = deps_parser.ParseDEPSContent('', keys=['skip_child_includes'])
    self.assertEqual(1, len(result))
    self.assertEqual([], result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            skip_child_includes = [
              'breakpad',
            ]"""),
        keys=['skip_child_includes'])
    expected_skip_child_includes = ['breakpad']
    self.assertEqual(1, len(result))
    self.assertEqual(expected_skip_child_includes, result[0])

  def testParseHooks(self):
    result = deps_parser.ParseDEPSContent('', keys=['hooks'])
    self.assertEqual(1, len(result))
    self.assertEqual([], result[0])

    result = deps_parser.ParseDEPSContent(
        textwrap.dedent("""
            hooks = [
              {
                # testing
                'name': 'testing',
                'pattern': '.',
                'action': [
                    'python',
                    'src/test.py',
                ],
              },
            ]"""),
        keys=['hooks'])
    expected_hooks = [
        {
            'name': 'testing',
            'pattern': '.',
            'action': [
                'python',
                'src/test.py',
            ],
        },
    ]
    self.assertEqual(1, len(result))
    self.assertEqual(expected_hooks, result[0])

  def testMergeWithOsDeps(self):
    """Verifies that complicated deps_os constructs result in the
    correct data also with multiple operating systems."""
    # This test is copied from gclient_test.py with little change.

    test_data = [
        # Tuples of deps, deps_os, os_list and expected_deps.
        (
            # OS doesn't need module.
            {'foo': 'default_foo'},
            {'os1': { 'foo': None } },
            ['os1'],
            {'foo': None}
        ),
        (
            # OS wants a different version of module.
            {'foo': 'default_foo'},
            {'os1': { 'foo': 'os1_foo'} },
            ['os1'],
            {'foo': 'os1_foo'}
        ),
        (
            # OS with no overrides at all.
            {'foo': 'default_foo'},
            {'os1': { 'foo': None } },
            ['os2'],
            {'foo': 'default_foo'}
        ),
        (
            # One OS doesn't need module, one OS wants the default.
            {'foo': 'default_foo'},
            {'os1': { 'foo': None },
             'os2': {}},
            ['os1', 'os2'],
            {'foo': 'default_foo'}
        ),
        (
            # One OS doesn't need module, another OS wants a special version.
            {'foo': 'default_foo'},
            {'os1': { 'foo': None },
             'os2': { 'foo': 'os2_foo'}},
            ['os1', 'os2'],
            {'foo': 'os2_foo'}
        ),
        (
            # One OS wants to add a module.
            {'foo': 'default_foo'},
            {'os1': { 'bar': 'os1_bar' }},
            ['os1'],
            {'foo': 'default_foo',
             'bar': 'os1_bar'}
        ),
        (
            # One OS wants to add a module. One doesn't care.
            {'foo': 'default_foo'},
            {'os1': { 'bar': 'os1_bar' }},
            ['os1', 'os2'],
            {'foo': 'default_foo',
             'bar': 'os1_bar'}
        ),
        (
            # Two OSes want to add a module with the same definition.
            {'foo': 'default_foo'},
            {'os1': { 'bar': 'os12_bar' },
             'os2': { 'bar': 'os12_bar' }},
            ['os1', 'os2'],
            {'foo': 'default_foo',
             'bar': 'os12_bar'}
        ),
        (
            # Two OSes want different versions of the same module.
            {'foo': 'default_foo'},
            {'os1': { 'bar': 'os_bar1' },
             'os2': { 'bar': 'os_bar2' }},
            ['os2', 'os1'],
            {'foo': 'default_foo',
             'bar': 'os_bar1'}
        ),
      ]

    for deps, deps_os, target_os_list, expected_deps in test_data:
      orig_deps = copy.deepcopy(deps)
      orig_deps_os = copy.deepcopy(deps_os)
      result = deps_parser.MergeWithOsDeps(deps, deps_os, target_os_list)
      self.assertEqual(result, expected_deps)
      self.assertEqual(deps, orig_deps)
      self.assertEqual(deps_os, orig_deps_os)

  def testUpdateDependencyTree(self):
    root_dep_path = 'src/'
    root_dep_repo_url = 'https://src.git'
    root_dep_revision = '1234src'
    root_dep_deps_file = 'DEPS'

    class DummyDEPSLoader(deps_parser.DEPSLoader):
      def __init__(self, test):
        self.test = test

      def Load(self, repo_url, revision, deps_file):
        self.test.assertEqual(root_dep_repo_url, repo_url)
        self.test.assertEqual(root_dep_revision, revision)
        self.test.assertEqual(root_dep_deps_file, deps_file)

        return textwrap.dedent("""
            deps = {
              'src/a/': 'https://a.git@1234a',
              'src/b': 'https://b.git',
            }

            deps_os = {
              'win': {
                'src/b': None,
              },
              'unix': {
                'src/b': None,
                'src/c': 'https://c.git@1234c'
              },
              'mac': {
                'src/d': 'https://d.git@1234d'
              }
            }""")

    expected_deps_tree_json_unix = {
        'path': root_dep_path,
        'repo_url': root_dep_repo_url,
        'revision': root_dep_revision,
        'deps_file': root_dep_deps_file,
        'children': {
            'src/a/': {
                'path': 'src/a/',
                'repo_url': 'https://a.git',
                'revision': '1234a',
                'deps_file': root_dep_deps_file,
                'children': {
                }
            },
            'src/c/': {
                'path': 'src/c/',
                'repo_url': 'https://c.git',
                'revision': '1234c',
                'deps_file': root_dep_deps_file,
                'children': {
                }
            },
        }
    }
    expected_deps_tree_json_win = {
        'path': root_dep_path,
        'repo_url': root_dep_repo_url,
        'revision': root_dep_revision,
        'deps_file': root_dep_deps_file,
        'children': {
            'src/a/': {
                'path': 'src/a/',
                'repo_url': 'https://a.git',
                'revision': '1234a',
                'deps_file': root_dep_deps_file,
                'children': {
                }
            }
        }
    }
    expected_deps_tree_json_all = {
        'path': root_dep_path,
        'repo_url': root_dep_repo_url,
        'revision': root_dep_revision,
        'deps_file': root_dep_deps_file,
        'children': {
            'src/a/': {
                'path': 'src/a/',
                'repo_url': 'https://a.git',
                'revision': '1234a',
                'deps_file': root_dep_deps_file,
                'children': {
                }
            },
            'src/b/': {
                'path': 'src/b/',
                'repo_url': 'https://b.git',
                'revision': None,
                'deps_file': root_dep_deps_file,
                'children': {
                }
            },
            'src/c/': {
                'path': 'src/c/',
                'repo_url': 'https://c.git',
                'revision': '1234c',
                'deps_file': root_dep_deps_file,
                'children': {
                }
            },
            'src/d/': {
                'path': 'src/d/',
                'repo_url': 'https://d.git',
                'revision': '1234d',
                'deps_file': root_dep_deps_file,
                'children': {
                }
            },
        }
    }


    def _Test(target_os_list, expected_deps_tree_json):
      root_dep = dependency.Dependency(
          root_dep_path, root_dep_repo_url, root_dep_revision,
          root_dep_deps_file)

      deps_parser.UpdateDependencyTree(
          root_dep, target_os_list, DummyDEPSLoader(self))

      self.assertEqual(expected_deps_tree_json, root_dep.ToDict())

    _Test(['unix'], expected_deps_tree_json_unix)
    _Test(['win'], expected_deps_tree_json_win)
    _Test(['all', 'win'], expected_deps_tree_json_all)
