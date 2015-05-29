# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import posixpath
import shutil

from collections import OrderedDict

from infra.libs.git2 import repo
from infra.libs.git2.testing_support import GitEntry
from infra_libs.infra_types import thaw

GSUBTREED_TESTS = {}
def test(f):
  GSUBTREED_TESTS[f.__name__] = f
  return f


@test
def path_map_exceptions(origin, run, checkpoint, mirrors, **_):
  master = origin['refs/heads/master']
  mc = master.make_commit
  mc('first commit', {'exception': {'path': {'file': 'cowabunga'}}})

  checkpoint('repo is set up')
  run()
  checkpoint('should see stuff')

  assert GitEntry.spec_for(mirrors['cool_path'], 'refs/heads/master') == {
    'file': ('cowabunga', 0644),
  }


@test
def master_mirrored_path(origin, run, checkpoint, mirrors, **_):
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

  assert GitEntry.spec_for(mirrors['mirrored_path'], 'refs/heads/master') == {
    'mirror_file': ('awesome sauce', 0644),
    'some_other_file': ('neat', 0644),
  }


@test
def multiple_refs(origin, run, checkpoint, mirrors, **_):
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

  spec = GitEntry.spec_for(mirrors['mirrored_path/subpath'], 'refs/heads/other')
  assert spec == {
    'nested': ('data in a subdir!?', 0644)
  }


@test
def mirrored_path_is_a_file(origin, run, checkpoint, mirrors, **_):
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

  assert GitEntry.spec_for(mirrors['mirrored_path'], 'refs/heads/master') == {
    'what what': ('datars!', 0644)
  }


@test
def multiple_runs(origin, run, checkpoint, mirrors, **_):
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

  spec = GitEntry.spec_for(mirrors['mirrored_path/subpath'], 'refs/heads/other')
  assert spec == {
    'nested': ('data in a subdir!?', 0644)
  }

  mc('new_commit', {'mirrored_path': {'whatpath': {'nested': 'datas'}}})
  checkpoint('added new_commit')
  run()
  checkpoint('should gain new synthed commit')


@test
def fix_footers(origin, run, checkpoint, mirrors, **_):
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

  assert GitEntry.spec_for(mirrors['mirrored_path'], 'refs/heads/branch') == {
    'sweet': ('totally!', 0644)
  }
  footers = mirrors['mirrored_path']['refs/heads/branch'].commit.data.footers
  assert thaw(footers) == OrderedDict([
    ('Commit-Id', ['whaaat']),
    ('Cr-Original-Commit-Position', ['refs/heads/branch@{#12345}']),
    ('Cr-Original-Branched-From', ['deadbeef-refs/heads/master@{#12300}']),
    ('Cr-Mirrored-From', ['[FILE-URL]']),
    ('Cr-Mirrored-Commit', ['b404e807c89d3b8f4b255fec1aaa9e123808f63c']),
  ])


@test
def halt_on_bad_mirror_commit(origin, run, checkpoint, mirrors,
                              config, local_origin_repo, **_):
  master = origin['refs/heads/master']
  master.make_commit('initial commit', {'mirrored_path': {'file': 'data'}})

  checkpoint('a single commit')
  run()
  checkpoint('a single mirrored commit')

  footers = mirrors['mirrored_path']['refs/heads/master'].commit.data.footers
  assert thaw(footers) == OrderedDict([
    ('Cr-Mirrored-From', ['[FILE-URL]']),
    ('Cr-Mirrored-Commit', ['7002d44b73ea8a85ee2b3e8f5f81c8c5d2ff557a']),
  ]), footers

  mhead = mirrors['mirrored_path']['refs/heads/master']
  mhead.update_to(mhead.commit.alter(
    footers={
      'Cr-Mirrored-Commit': ['deadbeefdeadbeefdeadbeefdeadbeefdeadbeef']
    }
  ))

  # force a resync of gsubtreed's local copy of the mirrored_path subtree repo.
  base_url = config['base_url']
  subtree_repo = repo.Repo(posixpath.join(base_url, 'mirrored_path'))
  subtree_repo.repos_dir = local_origin_repo.repos_dir
  subtree_repo.reify(share_from=local_origin_repo)
  shutil.rmtree(subtree_repo.repo_path)

  checkpoint('altered mirrored commit')
  run()
  checkpoint('should have bonked out')


@test
def bootstrap_fails_without_footer(origin, run, checkpoint, mirrors, **_):
  master = origin['refs/heads/master']
  mirrored_path_repo = mirrors['mirrored_path']
  mirrored_path = mirrored_path_repo['refs/heads/master']
  mc = master.make_commit
  mpc = mirrored_path.make_commit

  mc('initial commit', {'mirrored_path': {'file': 'data'}})
  mc('second commit', {'mirrored_path': {'other': 'hat'}})
  mpc('initial commit', {'file': 'data'})

  checkpoint('mirrored_path repo bootstrapped')
  run()
  checkpoint('mirrored_path repo should not have changed')

  assert GitEntry.spec_for(mirrored_path_repo, 'refs/heads/master') == {
    'file': ('data', 0644),
  }


@test
def bootstrap_history_with_extra_footers(origin, run, checkpoint, mirrors, **_):
  master = origin['refs/heads/master']
  mirrored_path_repo = mirrors['mirrored_path']
  mirrored_path = mirrored_path_repo['refs/heads/master']
  mc = master.make_commit
  mpc = mirrored_path.make_commit

  initial = mc('initial commit', {'mirrored_path': {'file': 'data'}})
  mc('second commit', {'mirrored_path': {'other': 'hat'}})
  mpc('initial commit', {'file': 'data'})

  # Deterministically create note commit
  mirrored_path_repo['refs/notes/extra_footers'].make_commit(
    'Notes added by \'git notes add\'',
    {mirrored_path.commit.hsh: 'Cr-Mirrored-Commit: %s' % initial.hsh}
  )

  checkpoint('mirrored_path repo bootstrapped')
  run()
  checkpoint('mirrored_path repo should have second commit')

  assert GitEntry.spec_for(mirrored_path_repo, 'refs/heads/master') == {
    'file': ('data', 0644),
    'other': ('hat', 0644)
  }


@test
def deleted_tree_is_ok(origin, run, checkpoint, mirrors, **_):
  master = origin['refs/heads/master']
  mc = master.make_commit
  mc('first commit', {'mirrored_path': {'file': 'data'}})
  mc('revert first commit', {'mirrored_path': None})
  mc('first commit again', {'mirrored_path': {'file': 'new data'}})

  checkpoint('repo is set up')
  run()
  checkpoint('should see stuff')

  assert GitEntry.spec_for(mirrors['mirrored_path'], 'refs/heads/master') == {
    'file': ('new data', 0644),
  }


@test
def multi_push(origin, run, checkpoint, mirrors, config, **_):
  config.update(path_extra_push={
    'mirrored_path': [mirrors['extra_mirror'].repo_path]})

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

  assert GitEntry.spec_for(mirrors['mirrored_path'], 'refs/heads/master') == {
    'mirror_file': ('awesome sauce', 0644),
    'some_other_file': ('neat', 0644),
  }
  assert GitEntry.spec_for(mirrors['extra_mirror'], 'refs/heads/master') == {
    'mirror_file': ('awesome sauce', 0644),
    'some_other_file': ('neat', 0644),
  }
