# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from infra.services.gnumbd import gnumbd
content_of = gnumbd.content_of

REAL = 'refs/heads/master'
PEND = 'refs/pending/heads/master'
PEND_TAG = 'refs/pending-tags/heads/master'

BRANCH = 'refs/branch-heads/cool_branch'
BRANCH_PEND = 'refs/pending/branch-heads/cool_branch'
BRANCH_TAG = 'refs/pending-tags/branch-heads/cool_branch'


GNUMBD_TESTS = {}
def gnumbd_test(f):
  GNUMBD_TESTS[f.__name__] = f
  return f


def svn_footers(num):
  return {
    gnumbd.GIT_SVN_ID: [
      'svn://repo/path@%s 0039d316-1c4b-4281-b951-d872f2087c98' % num]
  }


def gnumbd_footers(ref, num):
  return {
    gnumbd.COMMIT_POSITION: [gnumbd.FMT_COMMIT_POSITION(ref, num)]
  }


# Error cases
@gnumbd_test
def no_real_ref(origin, _local, _config_ref, RUN, CHECKPOINT):
  origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('One commit in origin')
  RUN()
  CHECKPOINT('Origin should not have changed')


@gnumbd_test
def no_pending_tag(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  origin[PEND].fast_forward(base_commit)
  origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Two commits in origin')
  RUN()
  CHECKPOINT('Origin should not have changed')


@gnumbd_test
def bad_position_footer(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
      'Base commit', footers={gnumbd.COMMIT_POSITION: ['BlobbyGumpus!']})
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Bad master commit footer')
  RUN()
  CHECKPOINT('Should be the same')
  assert origin[REAL].commit == base_commit


@gnumbd_test
def bad_svn_footer(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
      'Base commit', footers={gnumbd.GIT_SVN_ID: ['BlobbyGumpus!']})
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Bad master commit footer')
  RUN()
  CHECKPOINT('Should be the same')
  assert origin[REAL].commit == base_commit


@gnumbd_test
def no_position_footer(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
      'Base commit', footers={'Sup': ['Not a footer']})
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Master has no position footer')
  RUN()
  CHECKPOINT('Should be the same')
  assert origin[REAL].commit == base_commit


@gnumbd_test
def merge_commits_fail(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  o_commit = origin['refs/heads/other'].make_full_tree_commit(
    'Incoming merge!', footers=gnumbd_footers(origin['refs/heads/other'], 20))
  m_commit = base_commit.alter(
      parents=(base_commit.hsh, o_commit.hsh),
      message_lines=['Two for one!'],
      footers={k: None for k in base_commit.data.footers}
  )

  origin[PEND].fast_forward(m_commit)
  origin[PEND].make_full_tree_commit('Hello world')

  CHECKPOINT('The setup.')
  RUN()
  CHECKPOINT('Should be the same')


@gnumbd_test
def manual_merge_commits_ok(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))

  o_commit = origin['refs/heads/other'].make_full_tree_commit(
    'Incoming merge!', footers=gnumbd_footers(origin['refs/heads/other'], 20))
  footers = {k: None for k in base_commit.data.footers}
  footers[gnumbd.COMMIT_POSITION] = ['refs/heads/master@{#101}']

  m_commit = base_commit.alter(
      parents=(base_commit.hsh, o_commit.hsh),
      message_lines=['Two for one!'],
      footers=footers
  )
  origin[REAL].fast_forward(m_commit)
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(m_commit)

  origin[PEND].make_full_tree_commit('Hello world')

  CHECKPOINT('The setup.')
  RUN()
  CHECKPOINT('Hello world landed w/o a hitch')


@gnumbd_test
def no_number_on_parent(origin, local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit('Base without number')
  user_commit = origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('One commit in origin')
  RUN()
  CHECKPOINT('Should still only have 1 commit')
  assert local[PEND].commit == user_commit
  assert local[REAL].commit == base_commit


# Normal cases
@gnumbd_test
def incoming_svn_id_drops(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=svn_footers(100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Two commits in origin')
  RUN()
  CHECKPOINT('Hello world should be 101')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit


# pending > master == tag
@gnumbd_test
def normal_update(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Two commits')
  RUN()
  CHECKPOINT('Hello world should be 101')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit


# master == pending == tag
@gnumbd_test
def steady_state(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit('Hello world')
  RUN(include_log=False)
  CHECKPOINT('Hello world should be 101')
  RUN()
  CHECKPOINT('Hello world should still be 101')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit


# master == pending > tag
@gnumbd_test
def tag_lagging_no_actual(origin, _local, _config_ref, RUN, CHECKPOINT):
  origin[REAL].make_full_tree_commit(
    'Root commit', footers=gnumbd_footers(origin[REAL], 99))
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit('Hello world')

  RUN(include_log=False)
  origin[PEND_TAG].update_to(origin[PEND_TAG].commit.parent.parent)

  CHECKPOINT('Tag on root (2 behind pend)')
  RUN()
  CHECKPOINT('Tag caught up')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit
  assert origin[PEND_TAG].commit == origin[PEND].commit


# pending > master > tag
@gnumbd_test
def tag_lagging(origin, _local, _config_ref, RUN, CHECKPOINT):
  origin[REAL].make_full_tree_commit(
    'Root commit', footers=gnumbd_footers(origin[REAL], 99))
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')

  RUN(include_log=False)
  landed_commit = origin[REAL].commit

  origin[PEND_TAG].update_to(origin[PEND_TAG].commit.parent.parent)
  user_commit = origin[PEND].make_full_tree_commit('New commit')

  CHECKPOINT('Tag on root (3 behind pend). Real 1 behind pend')
  RUN()
  CHECKPOINT('Tag + pending caught up')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == landed_commit
  assert origin[PEND_TAG].commit == origin[PEND].commit


@gnumbd_test
def multi_pending(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit1 = origin[PEND].make_full_tree_commit('Hello world')
  user_commit2 = origin[PEND].make_full_tree_commit('Cat food')
  CHECKPOINT('Two pending commits')
  RUN()
  CHECKPOINT('And now they\'re on master')
  assert content_of(origin[REAL].commit.parent) == content_of(user_commit1)
  assert content_of(origin[REAL].commit) == content_of(user_commit2)
  assert origin[REAL].commit.parent.parent == base_commit


# Inconsistency

# tag > pending
# Implicitly covers:
#   * master > tag > pending
#   * tag > pending > master
#   * tag > master > pending
#   * tag > pending == master
@gnumbd_test
def master_tag_ahead_pending(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  RUN(include_log=False)

  origin[PEND].update_to(base_commit)
  CHECKPOINT('Master and tag ahead of pending')
  RUN()
  CHECKPOINT('Should see errors and no change')


# pending > tag > master
@gnumbd_test
def normal_with_master_lag(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  RUN(include_log=False)

  # master moves back
  origin[REAL].update_to(base_commit)

  # pending gets a new commit
  origin[PEND].make_full_tree_commit('New pending')

  CHECKPOINT('Master is behind, pending is ahead of tag')
  RUN()
  CHECKPOINT('Should see errors and no change')

  # fix by rewinding tag
  origin[PEND_TAG].update_to(origin[PEND_TAG].commit.parent)
  CHECKPOINT('Fix by rewinding tag')
  RUN()
  CHECKPOINT('All better')


@gnumbd_test
def master_ahead_tag_ahead_pending(origin, _local, _config_ref, RUN,
                                   CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[REAL].make_full_tree_commit('Directly landed commit!')
  origin[PEND_TAG].make_full_tree_commit('Tag ahead of pending')

  CHECKPOINT('Master and tag have diverged, pend lags')
  RUN()
  CHECKPOINT('Should have errored and nothing changed')


# master > pending == tag
@gnumbd_test
def master_ahead(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  base_commit = origin[REAL].make_full_tree_commit('Directly landed commit!')

  CHECKPOINT('Master contains a commit whose content isn\'t in pending')
  RUN()
  CHECKPOINT('Should have errored and nothing changed')
  assert origin[REAL].commit == base_commit


# pending == tag > master
@gnumbd_test
def master_behind(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit('Hello world')
  origin[PEND_TAG].fast_forward(user_commit)
  CHECKPOINT('Master should have new commit but does not')
  RUN()
  CHECKPOINT('Error and no change')


# master > pending > tag
@gnumbd_test
def master_mismatch_and_pend(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)
  origin[PEND].make_full_tree_commit('Hello world')

  base_commit = origin[REAL].make_full_tree_commit('Directly landed commit!')

  CHECKPOINT('Master contains a commit whose content isn\'t in pending')
  RUN()
  CHECKPOINT('Should have errored and nothing changed')
  assert origin[REAL].commit == base_commit


# Branching
@gnumbd_test
def branch(origin, _local, config_ref, RUN, CHECKPOINT):
  new_globs = config_ref['enabled_refglobs'] + ['refs/branch-heads/*']
  config_ref.update(enabled_refglobs=new_globs)

  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  CHECKPOINT('Pending commit', include_config=True)
  RUN()
  CHECKPOINT('And now it\'s on master', include_config=True)

  # Build a new branch
  for ref in (BRANCH, BRANCH_TAG, BRANCH_PEND):
    origin[ref].fast_forward(origin[REAL].commit)

  origin[BRANCH_PEND].make_full_tree_commit('Branch commit!')
  CHECKPOINT('New branch with pending', include_config=True)
  RUN()
  CHECKPOINT('Pending commit now on branch', include_config=True)

  origin[BRANCH_PEND].make_full_tree_commit('Another branch commit')
  CHECKPOINT('New pending commit for branch', include_config=True)
  RUN()
  CHECKPOINT('Second pending commit now on branch', include_config=True)

  assert origin[BRANCH].commit.data.footers[gnumbd.BRANCHED_FROM] == (
      '%s-%s' % (
          origin[REAL].commit.hsh,
          origin[REAL].commit.data.footers[gnumbd.COMMIT_POSITION][0]
      ),
  )


@gnumbd_test
def branch_from_branch(origin, _local, config_ref, RUN, CHECKPOINT):
  new_globs = config_ref['enabled_refglobs'] + ['refs/branch-heads/*']
  config_ref.update(enabled_refglobs=new_globs)

  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit('Hello world')
  RUN(include_log=False)

  # Build a new branch
  for ref in (BRANCH, BRANCH_TAG, BRANCH_PEND):
    origin[ref].fast_forward(origin[REAL].commit)

  origin[BRANCH_PEND].make_full_tree_commit('Branch commit!')
  RUN(include_log=False)

  CHECKPOINT('Branch 1 in place', include_config=True)

  yo_branch = BRANCH+'_yo'
  yo_branch_tag = BRANCH_TAG+'_yo'
  yo_branch_pend = BRANCH_PEND+'_yo'
  for ref in (yo_branch, yo_branch_tag, yo_branch_pend):
    origin[ref].fast_forward(origin[BRANCH].commit)

  origin[yo_branch_pend].make_full_tree_commit('Super branchey commit')
  CHECKPOINT('New pending commit for branch', include_config=True)
  RUN()
  CHECKPOINT('Second pending commit now on branch', include_config=True)

  assert origin[yo_branch].commit.data.footers[gnumbd.BRANCHED_FROM] == (
      '%s-%s' % (
          origin[BRANCH].commit.hsh,
          origin[BRANCH].commit.data.footers[gnumbd.COMMIT_POSITION][0]
      ),
      '%s-%s' % (
          origin[REAL].commit.hsh,
          origin[REAL].commit.data.footers[gnumbd.COMMIT_POSITION][0]
      ),
  )


# Extra footers
@gnumbd_test
def extra_user_footer(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit(
      'Hello world', footers=collections.OrderedDict([
          ('Change-Id', ['Icafebabe1cec6eadfeba']),
          ('Reviewed-by', [
              'Cool Dudette 64 <cd64@example.com>',
              'Epic Sky Troll <est@example.com>',
          ]),
          ('Tested-by', ['Lol JK <lol_jk@example.com>'])
      ]))
  CHECKPOINT('The setup...')
  RUN()
  CHECKPOINT('The new footers should appear after the current ones')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit


@gnumbd_test
def extra_user_footer_bad(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit(
      'Hello world', footers=collections.OrderedDict([
          ('Cr-Double-Secret', ['I can impersonate the daemon!']),
          ('git-svn-id', ['Well... this should never happen'])
      ]))
  CHECKPOINT('Two commits')
  RUN()
  CHECKPOINT('The bogus footers should be gone')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.data.footers == {
      gnumbd.COMMIT_POSITION: (gnumbd.FMT_COMMIT_POSITION(origin[REAL], 101),)
  }


@gnumbd_test
def enforce_commit_timestamps(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=gnumbd_footers(origin[REAL], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  # cheat and rewind the TestClock
  origin._clock._time -= 100  # pylint: disable=W0212

  user_commit = origin[PEND].make_full_tree_commit('Hello world')
  assert (
      user_commit.data.committer.timestamp.secs <
      base_commit.data.committer.timestamp.secs
  )

  CHECKPOINT('%r has a timestamp behind %r' % (
      user_commit.hsh, base_commit.hsh), include_committer=True)
  RUN()
  CHECKPOINT('Presto! Timestamp is fixed', include_committer=True)
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit
  assert (
      origin[REAL].commit.data.committer.timestamp.secs >
      origin[REAL].commit.parent.data.committer.timestamp.secs
  )


# git_svn_mode test.

@gnumbd_test
def svn_mode_uses_svn_rev(origin, _local, config_ref, RUN, CHECKPOINT):
  config_ref.update(git_svn_mode=True)

  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=svn_footers(100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit(
    'Hello world', footers=svn_footers(200))
  CHECKPOINT('Two commits in origin')
  RUN()
  CHECKPOINT('Hello world should be 200')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit


@gnumbd_test
def push_extra(origin, _local, config_ref, RUN, CHECKPOINT):
  config_ref.update(
    git_svn_mode=True,
    push_synth_extra={
      'refs/heads/master': ['refs/heads/crazy-times']
    }
  )

  base_commit = origin[REAL].make_full_tree_commit(
    'Base commit', footers=svn_footers(100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  user_commit = origin[PEND].make_full_tree_commit(
    'Hello world', footers=svn_footers(200))
  CHECKPOINT('Two commits in origin')
  RUN()
  CHECKPOINT('Should have crazy-times')
  assert content_of(origin[REAL].commit) == content_of(user_commit)
  assert origin[REAL].commit.parent == base_commit


@gnumbd_test
def cherry_pick_regression(origin, _local, _config_ref, RUN, CHECKPOINT):
  base_commit = origin[REAL].make_full_tree_commit(
    'Numbered commit', footers=gnumbd_footers(
      origin['refs/branch-heads/1'], 100))
  for ref in (PEND, PEND_TAG):
    origin[ref].fast_forward(base_commit)

  origin[PEND].make_full_tree_commit(
    'cherry pick', footers=gnumbd_footers(origin[REAL], 200))

  origin[PEND].make_full_tree_commit('normal commit')

  CHECKPOINT('OK commit with cherrypick (including cr-commit-pos)')
  RUN()
  CHECKPOINT('Cherry pick\'s number should be overwritten')
