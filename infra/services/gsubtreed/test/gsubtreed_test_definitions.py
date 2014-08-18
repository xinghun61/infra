# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra.libs.git2.testing_support import GitEntry

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
