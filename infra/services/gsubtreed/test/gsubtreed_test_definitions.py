# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import OrderedDict

from infra.libs.git2.testing_support import GitEntry
from infra.libs.infra_types import thaw

GSUBTREED_TESTS = {}
def test(f):
  GSUBTREED_TESTS[f.__name__] = f
  return f


@test
def master_mirrored_path(origin, run, checkpoint):
  master = origin['refs/heads/master']
  mc = master.make_commit
  mc('first commit', {'unrelated': 'cowabunga'})
  mc('next commit', {
    'mirrored_path': {
      'mirror_file': 'awesome sauce',
      'some_other_file': 'neat',
    },
    'unrelated': 'other',
    'unrelated_path': 'not helpful',
  })
  master.make_commit('unrelated commit', {
    'unrelated_path': 'helpful?',
  })

  checkpoint('repo is set up')
  run()
  checkpoint('should see stuff')

  synthed = 'refs/subtree-synthesized/mirrored_path/-/heads/master'
  assert GitEntry.spec_for(origin, synthed) == {
    'mirror_file': ('awesome sauce', 0644),
    'some_other_file': ('neat', 0644),
  }


@test
def multiple_refs(origin, run, checkpoint):
  master = origin['refs/heads/master']
  other = origin['refs/heads/other']
  mc = master.make_commit
  oc = other.make_commit

  mc('nerd_commit', {'mirrored_path': {'sweet subfile': 'nerds'}})
  oc('what_commit', {
    'mirrored_path': {
      'sweet subfile': 'what',
      'subpath': {
        'nested': 'data in a subdir!?'}}})

  checkpoint('all set up')
  run()
  checkpoint('lots refs')

  synthed = 'refs/subtree-synthesized/mirrored_path/subpath/-/heads/other'
  assert GitEntry.spec_for(origin, synthed) == {
    'nested': ('data in a subdir!?', 0644)
  }


@test
def mirrored_path_is_a_file(origin, run, checkpoint):
  master = origin['refs/heads/master']
  mc = master.make_commit
  mc('first commit', {'unrelated': 'cowabunga'})
  mc('bad subtree', {'mirrored_path': 'it\'s a file!!'})
  mc('but now it\'s OK', {'mirrored_path': {'silly': 'data'}})
  mc('now it\'s a file again', {'mirrored_path': 'fail!'})
  mc('back to a dir', {'mirrored_path': {'what what': 'datars!'}})

  checkpoint('repo is set up')
  run()
  checkpoint('should see 2 commits in synthesized')

  synthed = 'refs/subtree-synthesized/mirrored_path/-/heads/master'
  assert GitEntry.spec_for(origin, synthed) == {
    'what what': ('datars!', 0644)
  }


@test
def multiple_runs(origin, run, checkpoint):
  master = origin['refs/heads/master']
  other = origin['refs/heads/other']
  mc = master.make_commit
  oc = other.make_commit

  mc('nerd_commit', {'mirrored_path': {'sweet subfile': 'nerds'}})
  oc('what_commit', {
    'mirrored_path': {
      'sweet subfile': 'what',
      'subpath': {
        'nested': 'data in a subdir!?'}}})

  checkpoint('all set up')
  run()
  checkpoint('lots refs')

  synthed = 'refs/subtree-synthesized/mirrored_path/subpath/-/heads/other'
  assert GitEntry.spec_for(origin, synthed) == {
    'nested': ('data in a subdir!?', 0644)
  }

  mc('new_commit', {'mirrored_path': {'whatpath': {'nested': 'datas'}}})
  checkpoint('added new_commit')
  run()
  checkpoint('should gain new synthed commit')


@test
def fix_footers(origin, run, checkpoint):
  branch = origin['refs/heads/branch']
  branch.make_commit(
    'sweet commit',
    {'mirrored_path': {'sweet': 'totally!'}},
    OrderedDict([
      ('git-svn-id', ['totally annoying!']),
      ('Cr-Commit-Position', ['refs/heads/branch@{#12345}']),
      ('Commit-Id', ['whaaat']),
      ('Cr-Branched-From', ['deadbeef-refs/heads/master@{#12300}']),
    ]))

  checkpoint('a really sweet commit')
  run()
  checkpoint('a really sweet (mirrored) commit')

  synthed = 'refs/subtree-synthesized/mirrored_path/-/heads/branch'
  assert GitEntry.spec_for(origin, synthed) == {
    'sweet': ('totally!', 0644)
  }
  assert thaw(origin[synthed].commit.data.footers) == OrderedDict([
    ('Commit-Id', ['whaaat']),
    ('Cr-Original-Commit-Position', ['refs/heads/branch@{#12345}']),
    ('Cr-Original-Branched-From', ['deadbeef-refs/heads/master@{#12300}']),
    ('Cr-Mirrored-From', ['[FILE-URL]']),
    ('Cr-Mirrored-Commit', ['b404e807c89d3b8f4b255fec1aaa9e123808f63c']),
  ])
