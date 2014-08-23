# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gnumd (Git NUMber Daemon): Adds metadata to git commits as they land in
a primary repo.

This is a simple daemon which takes commits pushed to a pending ref, alters
their message with metadata, and then pushes the altered commits to a parallel
ref.
"""

import collections
import logging
import re
import time

from infra.libs import git2
from infra.libs import infra_types
from infra.libs.git2 import config_ref


LOGGER = logging.getLogger(__name__)


FOOTER_PREFIX = 'Cr-'
COMMIT_POSITION = FOOTER_PREFIX + 'Commit-Position'
# takes a Ref and a number
FMT_COMMIT_POSITION = '{.ref}@{{#{:d}}}'.format
BRANCHED_FROM = FOOTER_PREFIX + 'Branched-From'
GIT_SVN_ID = 'git-svn-id'


################################################################################
# ConfigRef
################################################################################

class GnumbdConfigRef(config_ref.ConfigRef):
  CONVERT = {
    'git_svn_mode': lambda self, val: bool(val),
    'interval': lambda self, val: float(val),
    'pending_tag_prefix': lambda self, val: str(val),
    'pending_ref_prefix': lambda self, val: str(val),
    'enabled_refglobs': lambda self, val: map(str, list(val)),
    'push_synth_extra': lambda self, val: dict(
      (str(k), [self.repo[r] for r in v])
      for k, v in val.iteritems()
    )
  }
  DEFAULTS = {
    # If git_svn_mode is True, the following happens:
    #  * git-svn-id footer is NOT stripped from the commit.
    #  * Cr-Commit-Position equals to SVN revision from git-svn-id footer.
    # TODO(vadimsh): Remove git_svn_mode support when no longer needed.
    'git_svn_mode': False,
    'interval': 5.0,
    'pending_tag_prefix': 'refs/pending-tags',
    'pending_ref_prefix': 'refs/pending',
    'enabled_refglobs': [],
    'push_synth_extra': {},
  }
  REF = 'refs/gnumbd-config/main'


################################################################################
# Exceptions
################################################################################

class MalformedPositionFooter(Exception):
  def __init__(self, commit, header, value):
    super(MalformedPositionFooter, self).__init__(
        'in {!r}: "{}: {}"'.format(commit, header, value))


class NoPositionData(Exception):
  def __init__(self, commit):
    super(NoPositionData, self).__init__(
        'No {!r} or git-svn-id found for {!r}'.format(COMMIT_POSITION, commit))


################################################################################
# Commit Manipulation
################################################################################

def content_of(commit):
  """Calculates the content of |commit| such that a gnumbd-landed commit and
  the original commit will compare as equals. Returns the content as a
  git2.CommitData object.

  This strips out:
    * The parent(s)
    * The committer date
    * footers beginning with 'Cr-'
    * the 'git-svn-id' footer.

  Stores a cached copy of the result data on the |commit| instance itself.
  """
  if commit is None:
    return git2.INVALID

  if not hasattr(commit, '_cr_content'):
    d = commit.data
    footers = infra_types.thaw(d.footers)
    footers[GIT_SVN_ID] = None
    for k in footers.keys():
      if k.startswith(FOOTER_PREFIX):
        footers[k] = None
    commit._cr_content = d.alter(
        parents=(),
        committer=d.committer.alter(timestamp=git2.data.NULL_TIMESTAMP),
        footers=footers)
  return commit._cr_content  # pylint: disable=W0212


def get_git_svn_rev(commit):
  """Extracts SVN revision from git-svn-id footer of a commit.

  Raises NoPositionData or MalformedPositionFooter on errors.
  """
  svn_pos = commit.data.footers.get(GIT_SVN_ID)
  if not svn_pos:
    raise NoPositionData(commit)
  assert len(svn_pos) == 1
  svn_pos = svn_pos[0]
  try:
    return int(svn_pos.split()[0].split('@')[1])
  except (IndexError, ValueError):
    raise MalformedPositionFooter(commit, GIT_SVN_ID, svn_pos)


def get_position(commit, _position_re=re.compile('^(.*)@{#(\d*)}$')):
  """Returns (ref, position number) for the given |commit|.

  Extracts them from Cr-Commit-Position footer (that looks like
  refs/heads/master@{#287136}). If it falls back to git-svn-id, it passes back
  None for ref, and relies on the caller to make its best guess.

  May raise the MalformedPositionFooter or NoPositionData exceptions.
  """
  current_pos = commit.data.footers.get(COMMIT_POSITION)
  if current_pos:
    assert len(current_pos) == 1
    current_pos = current_pos[0]

    m = _position_re.match(current_pos)
    if not m:
      raise MalformedPositionFooter(commit, COMMIT_POSITION, current_pos)
    parent_ref = commit.repo[m.group(1)]
    parent_num = int(m.group(2))
  else:
    # TODO(iannucci): Remove this and rely on a manual initial commit?
    parent_ref = None
    parent_num = get_git_svn_rev(commit)

  return parent_ref, parent_num


def synthesize_commit(commit, new_parent, ref, git_svn_mode, clock=time):
  """Synthesizes a new Commit given |new_parent| and ref.

  The new commit will contain a Cr-Commit-Position footer, and possibly
  Cr-Branched-From footers (if commit is on a branch).

  The new commit's committer date will also be updated to 'time.time()', or
  the new parent's date + 1, whichever is higher. This means that within
  a branch, commit timestamps will always increase (at least from the point
  where this daemon went into service).

  If git_svn_mode is False, uses parent's commit position to derive new commit
  position. Also git-svn-id footer will be stripped out.

  If git_svn_mode is True, uses SVN revision from git-svn-id footer: it sets
  the commit position number equal to the svn revision. Keeps git-svn-id footer.

  @type commit: git2.Commit
  @type new_parent: git2.Commit
  @type ref: git2.Ref
  @type git_svn_mode: bool
  @kind clock: implements .time(), used for testing determinism.
  """
  # Generate new footers.
  if git_svn_mode:
    git_svn_footer = commit.data.footers.get(GIT_SVN_ID)
    footers = generate_footers_from_git_svn_id(commit, new_parent, ref)
  else:
    git_svn_footer = None
    footers = generate_footers_from_parent(new_parent, ref)

  # TODO(iannucci): We could be more order-preserving of user supplied footers
  # but I'm inclined not to care. This loop will be enough to keep stuff from
  # Gerrit-landed commits.
  for key, value in commit.data.footers.iteritems():
    # In git_svn_mode drop git-svn-id silently, it's going to be added back.
    if git_svn_mode and key == GIT_SVN_ID:
      footers[key] = None
    elif key.startswith(FOOTER_PREFIX) or key == GIT_SVN_ID:
      LOGGER.warn('Dropping key on user commit %s: %r -> %r',
                  commit.hsh, key, value)
      footers[key] = None

  # Ensure that every commit has a time which is at least 1 second after its
  # parent, and reset the tz to UTC.
  parent_time = new_parent.data.committer.timestamp.secs
  new_parents = [] if new_parent is git2.INVALID else [new_parent.hsh]
  new_committer = commit.data.committer.alter(
      timestamp=git2.data.NULL_TIMESTAMP.alter(
          secs=max(int(clock.time()), parent_time + 1)))

  commit = commit.alter(
      parents=new_parents,
      committer=new_committer,
      footers=footers)

  # Slap back git-svn-id footer, do it as a separate operation to ensure it is
  # appended at the bottom of the footers list.
  if git_svn_mode and git_svn_footer:
    commit = commit.alter(footers={GIT_SVN_ID: git_svn_footer})

  return commit


def generate_footers_from_parent(new_parent, ref):
  """Generates Cr-Commit-Position footer, and possibly Cr-Branched-From footers.

  Uses parent's footers to derive new values.

  @returns OrderedDict.
  """
  # TODO(iannucci): See if there are any other footers we want to carry over
  # between new_parent and commit
  parent_ref, parent_num = get_position(new_parent)
  # if parent_ref wasn't encoded, assume that the parent is on the same ref.
  if parent_ref is None:
    parent_ref = ref

  footers = collections.OrderedDict()
  if parent_ref != ref:
    footers[COMMIT_POSITION] = [FMT_COMMIT_POSITION(ref, 1)]
    footers[BRANCHED_FROM] = [
        '%s-%s' % (new_parent.hsh, FMT_COMMIT_POSITION(parent_ref, parent_num))
    ] + list(new_parent.data.footers.get(BRANCHED_FROM, []))
  else:
    footers[COMMIT_POSITION] = [FMT_COMMIT_POSITION(ref, parent_num + 1)]
    footers[BRANCHED_FROM] = new_parent.data.footers.get(BRANCHED_FROM, ())

  return footers


def generate_footers_from_git_svn_id(commit, _new_parent, ref):
  """Generates Cr-Commit-Position footer from git-svn-id footer.

  Will never generate Cr-Branched-From footer.

  @returns OrderedDict.
  """
  svn_rev = get_git_svn_rev(commit)
  footers = collections.OrderedDict()
  footers[COMMIT_POSITION] = [FMT_COMMIT_POSITION(ref, svn_rev)]
  return footers


################################################################################
# Core functionality
################################################################################

def get_new_commits(real_ref, pending_tag, pending_tip):
  """Return a list of new pending commits to process or None on an error.

  Mutates pending_tag under some circumstances, see below.

  Ideally, real_ref, pending_tag and pending_tip should look something like:

        v  pending_tag
  A  B  C  D  E  F  <- pending_tip
  A' B' C' <- master

  And this method would return [D E F].

  If this arrangement is NOT the case, then this method can error out in a
  variety of ways, depending on how the repo is mangled. The most common cases
  are:

     v  pending_tag
  A  B  C  D  E  F  <- pending_tip
  A' B' C' <- master

  AND

     v  pending_tag
  A  B  C  D  E  F  <- pending_tip
  A' B' C' D' E' F' <- master

  In either case, pending_tag would be advanced, and the method would return
  the commits between the tag's proper position and the tip.

  Other discrepancies are errors and this method will return an empty list.

  @type pending_tag: git2.Ref
  @type pending_tip: git2.Ref
  @type real_ref: git2.Ref
  @returns [git2.Commit] or None
  """
  assert pending_tag.commit != pending_tip.commit
  new_commits = list(pending_tag.to(pending_tip))
  if not new_commits:
    LOGGER.error('%r doesn\'t match %r, but there are no new_commits?',
                 pending_tag.ref, pending_tip.ref)
    return None

  i = 0
  for commit in new_commits:
    parent = commit.parent
    if parent is git2.INVALID:
      LOGGER.error('Cannot process pending merge commit %r', commit)
      return None

    if content_of(parent) == content_of(real_ref.commit):
      break

    LOGGER.warn('Skipping already-processed commit on real_ref %r: %r',
                real_ref, commit.hsh)
    i += 1

  if i > 0:
    logging.warn('Catching up pending_tag %r (was %d behind)', pending_tag, i)
    new_tag_val = new_commits[i-1]
    if content_of(new_tag_val) != content_of(real_ref.commit):
      LOGGER.error('Content of new tag %r does not match content of %r!',
                   new_tag_val.hsh, real_ref.commit.hsh)
      return None
    new_commits = new_commits[i:]
    pending_tag.repo.queue_fast_forward({pending_tag: new_tag_val})

  if not new_commits:
    LOGGER.warn('Tag was lagging for %r by %d, but no new commits are pending',
                real_ref, len(new_commits))
    return []

  return new_commits


def process_ref(real_ref, pending_tag, new_commits, git_svn_mode,
                push_synth_extras, clock=time):
  """Given a |real_ref|, its corresponding |pending_tag|, and a list of
  |new_commits|, copy the |new_commits| to |real_ref|, and advance |pending_tag|
  to match.

  Assumes that pending_tag starts at the equivalent of real_ref, and that
  all commits in new_commits exist on pending_tag..pending_tip.

  Given:

        v  pending_tag
  A  B  C  D  E  F  <- pending_tip
  A' B' C' <- master

  This function will produce:

                 v  pending_tag
  A  B  C  D  E  F  <- pending_tip
  A' B' C' D' E' F' <- master

  @type real_ref: git2.Ref
  @type pending_tag: git2.Ref
  @type new_commits: [git2.Commit]
  @kind clock: implements .time(), used for testing determinism.
  @yields synthesized git2.Commit, pushes them to the remote as a side-effect.
  """
  # TODO(iannucci): use push --force-with-lease to reset pending to the real
  # ref?
  # TODO(iannucci): The ACL rejection message for the real ref should point
  # users to the pending ref.
  assert content_of(pending_tag.commit) == content_of(real_ref.commit)
  assert real_ref.repo is pending_tag.repo
  repo = real_ref.repo
  real_parent = real_ref.commit
  for commit in new_commits:
    assert content_of(commit.parent) == content_of(real_parent)
    synth_commit = synthesize_commit(
        commit, real_parent, real_ref, git_svn_mode, clock)

    logging.info(
        'Pushing synthesized commit %r for %r and pending_tag %r',
        synth_commit.hsh, commit.hsh, pending_tag)
    to_push = {
      real_ref: synth_commit,
      pending_tag: commit,
    }
    for extra_ref in push_synth_extras:
      # convert the extra_refs to Ref's on the local repo
      to_push[repo[extra_ref.ref]] = synth_commit
    repo.queue_fast_forward(to_push)

    real_parent = synth_commit
    yield synth_commit


def process_repo(repo, cref, clock=time):
  """Execute a single pass over a fetched Repo.

  Will call |process_ref| for every branch indicated by the enabled_refglobs
  config option.

  @returns tuple (bool success status, list of synthesized commits).
  """
  git_svn_mode = cref['git_svn_mode']
  pending_tag_prefix = cref['pending_tag_prefix']
  pending_ref_prefix = cref['pending_ref_prefix']
  enabled_refglobs = cref['enabled_refglobs']
  push_synth_extra = cref['push_synth_extra']

  def join(prefix, ref):
    assert ref.ref.startswith('refs/')
    return repo['/'.join((prefix, ref.ref[len('refs/'):]))]

  success = True
  synthesized_commits = []
  for refglob in enabled_refglobs:
    glob = join(pending_ref_prefix, repo[refglob])
    for pending_tip in repo.refglob(glob.ref):
      try:
        real_ref = git2.Ref(repo, pending_tip.ref.replace(
            pending_ref_prefix, 'refs'))

        if real_ref.commit is git2.INVALID:
          LOGGER.error('Missing real ref %r', real_ref)
          success = False
          continue

        LOGGER.info('Processing %r', real_ref)
        pending_tag = join(pending_tag_prefix, real_ref)

        if pending_tag.commit is git2.INVALID:
          LOGGER.error('Missing pending tag %r for %r', pending_tag, real_ref)
          success = False
          continue

        if pending_tag.commit != pending_tip.commit:
          new_commits = get_new_commits(real_ref, pending_tag, pending_tip)
          if new_commits is None:
            success = False
          elif new_commits:
            commits = process_ref(
                real_ref, pending_tag, new_commits, git_svn_mode,
                push_synth_extra.get(real_ref.ref, []), clock)
            synthesized_commits.extend(commits)
        else:
          if content_of(pending_tag.commit) != content_of(real_ref.commit):
            LOGGER.error('%r and %r match, but %r\'s content doesn\'t match!',
                         pending_tag, pending_tip, real_ref)
            success = False
          else:
            LOGGER.info('%r is up to date', real_ref)
      except (NoPositionData, MalformedPositionFooter) as e:
        LOGGER.error('%s %s', e.__class__.__name__, e)
        success = False
      except Exception:  # pragma: no cover
        LOGGER.exception('Uncaught exception while processing %r', real_ref)
        success = False
  return success, synthesized_commits


def inner_loop(repo, cref, clock=time):
  """Fetches the config ref and runs single iteration of processing.

  @returns tuple (bool success status, list of synthesized commits).
  """
  repo.fetch()
  cref.evaluate()
  commits = process_repo(repo, cref, clock)
  repo.push_queued_fast_forwards()
  return commits
