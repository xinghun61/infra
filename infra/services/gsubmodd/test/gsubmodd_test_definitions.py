# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from infra.libs.git2 import CalledProcessError
from infra.libs.git2 import EMPTY_TREE
from infra.libs.git2.testing_support import GitEntry

MASTER = 'refs/heads/master'

GSUBMODD_TESTS = {}
def test(f):
  GSUBMODD_TESTS[f.__name__] = f
  return f

@test
def hello_world(f):
  f.make_commit('first commit', {'abc': 'xyzzy'})
  f.checkpoint('b4')
  f.run()
  f.checkpoint('after')

  assert GitEntry.spec_for(f.target, MASTER) == {
      'abc': ('xyzzy', 0644),
  }


@test
def primitive_deps_file(f):
  # https://stackoverflow.com/a/1412728/98761 discusses textwrap.dedent()
  #
  deps_file_content = textwrap.dedent("""\
    deps = {
      "abc/def": "https://chromium.googlesource.com/xyz/foo@5d0be3947e7e238f38516eddbe286a61d3ec4bc9",
      "fount/foo": "https://chromoium.googlesource.com/xyz/bar@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  f.make_commit('initial commit',
     {
         'DEPS': deps_file_content,
         'in': {
             'bar': 'Hello, world'}})
  f.checkpoint('before')
  f.run()

  tree = GitEntry.spec_for(f.target, MASTER)
  gitmodules_file = tree.get('.gitmodules')[0]
  gitlink = tree.get('foo')
  f.checkpoint('after', gitmodules_file, gitlink)


@test
def gitlink_in_subdir(f):
  deps_file_content = textwrap.dedent("""\
    deps = {
      "fount/abc/pqr/wow": "http://chromium.googlesource.com/bar@4ebc8aea50e0a67e000ba29a30809d0a7b9b2666",
      "fount/ghi/aaa": "https://chromium.googlesource.com/yin@6ec0d686a7cd65baf620184617df1ed0f2828af3",
      "fount/abc/trl": "https://chromium.googlesource.com/foo@d020324450627468418945e0c7e53c0a141a3ab9",
      "fount/abc/def": "https://chromium.googlesource.com/foo@74bb638f337e6a79756595fae31737a8411a494b",
      "fount/ghi/zyx/deep": "https://chromium.googlesource.com/yin@da98e07bfc76bb53b8414656295e9b7ce9c00096",
    }
    """)
  f.make_commit('initial commit',
     {
         'DEPS': deps_file_content,
         'in': {
             'bar': 'Hello, world'}})
  f.checkpoint('before')
  f.run()

  tree = GitEntry.spec_for(f.target, MASTER)
  gitmodules_file = tree.get('.gitmodules')[0]
  subdir1 = tree.get('abc')
  subdir2 = tree.get('ghi')
  f.checkpoint('after', gitmodules_file, ('abc', subdir1), ('ghi', subdir2))

@test
def evolving_deps(f):
  """Dependencies which evolve over time, across separate calls."""

  # Initially, just one dep.
  deps1 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  tree = {
      'DEPS': deps1,
      'other': {'greeting.txt':'Hello, world!'}}
  f.make_commit('first', tree)
  tree['other']['README'] = '... (a file we added in the 2nd commit)'
  f.make_commit('second', tree)
  f.checkpoint('before')
  f.run()
  result_tree = GitEntry.spec_for(f.target, MASTER)
  gitmodules_file = result_tree.get('.gitmodules')[0]
  gitlinks = [result_tree.get(name) for name in ('foo',)]
  f.checkpoint('during', gitmodules_file, gitlinks)

  # Later, the "foo" dep has had its pinned SHA-1 modified, and a new
  # dep "bar" has been introduced.
  deps2 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@4ebc8aea50e0a67e000ba29a30809d0a7b9b2666",
      "fount/bar": "https://chromium.googlesource.com/bar@05c319264387a6c782f10c5e27e602ee36f98d0f",
    }
    """)
  tree['DEPS'] = deps2
  f.make_commit('third', tree)
  f.run()
  result_tree = GitEntry.spec_for(f.target, MASTER)
  gitmodules_file = result_tree.get('.gitmodules')[0]
  gitlinks = [result_tree.get(name) for name in ('foo', 'bar')]
  f.checkpoint('after', gitmodules_file, gitlinks)


@test
def evolving_deps_single(f):
  """Dependencies evolve within the time span of a single invocation."""
  deps1 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  tree = {
      'DEPS': deps1,
      'other': {'greeting.txt':'Hello, world!'}}
  f.make_commit('first', tree)

  deps2 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@4ebc8aea50e0a67e000ba29a30809d0a7b9b2666",
      "fount/bar": "https://chromium.googlesource.com/bar@05c319264387a6c782f10c5e27e602ee36f98d0f",
    }
    """)
  tree['DEPS'] = deps2
  f.make_commit('second', tree)
  f.checkpoint('before')
  f.run()
  result_tree = GitEntry.spec_for(f.target, MASTER)
  gitmodules_file = result_tree.get('.gitmodules')[0]
  gitlinks = [result_tree.get(name) for name in ('foo', 'bar')]
  f.checkpoint('after', gitmodules_file, gitlinks)


@test
def target_sync_lacks_footer(f):
  deps1 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  tree = {
      'DEPS': deps1,
      'other': {'greeting.txt':'Hello, world!'}}
  f.make_commit('first', tree)

  f.target[MASTER].make_commit('zeroth', {
      'LISEZMOI': 'somehow this unrelated commit got into the target repo'})
  f.checkpoint('before')
  f.run()  # TODO: verify that it returned False too
  f.checkpoint('after')


@test
def git_suffix(f):
  """Names the origin repo in the xxx.git format."""
  f._init_origin('fount.git')
  deps_file_content = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://chromoium.googlesource.com/xyz/bar@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  f.make_commit('initial commit',
     {
         'DEPS': deps_file_content,
         'in': {
             'bar': 'Hello, world'}})
  f.checkpoint('before')
  f.run()
  tree = GitEntry.spec_for(f.target, MASTER)
  gitmodules_file = tree.get('.gitmodules')[0]
  gitlink = tree.get('foo')
  f.checkpoint('after', gitmodules_file, gitlink)


@test
def spurious_sync(f):
  """Tries to sync to non-existent origin commit."""
  deps1 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  tree = {
      'DEPS': deps1,
      'other': {'greeting.txt':'Hello, world!'}}
  f.make_commit('first', tree)

  commit_msg = [
      'unrelated commit',
      '',
      'Cr-Mirrored-Commit: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
      ]
  f.target[MASTER].make_commit('\n'.join(commit_msg),
      {'README': 'nothing here!'})
  f.checkpoint('before')
  f.run()
  f.checkpoint('after')


@test
def idle(f):
  """Sometimes gsubmodd finds no work to do."""
  deps1 = textwrap.dedent("""\
    deps = {
      "fount/foo": "https://itdoesntmatter.com/xyzzy/foo@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  tree = {
      'DEPS': deps1,
      'other': {'greeting.txt':'Hello, world!'}}
  f.make_commit('first', tree)
  f.run()
  f.checkpoint('first')
  f.run()
  f.checkpoint('should be no difference')


@test
def epoch(f):
  """Specifies a starting point explicitly."""
  tree1 = {
      'other': {'greeting.txt':'Hello, world!'}}
  c = f.make_commit('first', tree1)
  start = c.hsh
  tree2 = {
      'other': {'greeting.txt':'Good-bye, cruel world!'}}
  f.make_commit('second', tree2)
  f.checkpoint('before')
  f.run(epoch=start)
  f.checkpoint('after')


@test
def epoch_nonexist(f):
  """Specifies a bogus starting point."""
  tree = {
      'other': {'greeting.txt':'Hello, world!'}}
  f.make_commit('first', tree)
  f.checkpoint('before')
  f.run(epoch=EMPTY_TREE)
  f.checkpoint('after')


# @test
# TODO(crbug/827587): enable this test when the bug is fixed
def removed(f):  # pragma: no cover
  """Last remaining dep is removed."""
  deps1 = textwrap.dedent("""\
    deps = {
      "abc/def": "https://chromium.googlesource.com/xyz/foo@5d0be3947e7e238f38516eddbe286a61d3ec4bc9",
      "fount/foo": "https://chromoium.googlesource.com/xyz/bar@10803d79ece6d8752be370163d342030a816cb8f",
    }
    """)

  f.make_commit('initial commit', {
         'DEPS': deps1,
         'subdir': {
             'bar': 'Hello, world'}})
  f.checkpoint('before')
  f.run()

  deps2 = textwrap.dedent("""\
    deps = {
      "abc/def": "https://chromium.googlesource.com/xyz/foo@5d0be3947e7e238f38516eddbe286a61d3ec4bc9",
    }
    """)
  f.make_commit('subsequent commit', {
         'DEPS': deps2,
         'subdir': {
             'bar': 'Hello, world'}})
  f.run()
  tree = GitEntry.spec_for(f.target, MASTER)
  assert not tree.get('.gitmodules')
  assert not tree.get('foo')
  f.checkpoint('after')


# TODO: test for dep pinned at symbolic ref should go in deps2submodules test
