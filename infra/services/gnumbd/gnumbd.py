# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gnumbd (Git NUMBer Daemon): Adds metadata to git commits as they land in
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
from infra.libs.git2 import data
from infra.libs.git2 import config_ref
from infra_libs import infra_types


LOGGER = logging.getLogger(__name__)


FOOTER_PREFIX = 'Cr-'
COMMIT_POSITION = FOOTER_PREFIX + 'Commit-Position'

# Takes a Ref and a integer and returns a formatted string
#:
FMT_COMMIT_POSITION = '{.ref}@{{#{:d}}}'.format
BRANCHED_FROM = FOOTER_PREFIX + 'Branched-From'
C_PICK = re.compile(r'\(cherry picked from commit [a-fA-F0-9]{40}\)')


# How long to wait for 'git push' to complete before forcefully killing it.
PUSH_TIMEOUT = 18 * 60

################################################################################
# ConfigRef
################################################################################

class GnumbdConfigRef(config_ref.ConfigRef):
  CONVERT = {
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
        'No {!r} found for {!r}'.format(COMMIT_POSITION, commit))


################################################################################
# Commit Manipulation
################################################################################


def tweak_cherry_pick(commit_data):
  # if there are no parsable footers, and the last line of the message
  # is a cherry pick notation, remove the cp line, and add it back with
  # a blank line to the message.
  d = commit_data
  if not d.footers and C_PICK.match(d.message_lines[-1]):
    cp_line = d.message_lines[-1]
    d = d.alter(message_lines=d.message_lines[:-1])
    d = data.CommitData.from_raw(str(d))

    new_lines = d.message_lines
    if not C_PICK.match(new_lines[-1]):
      new_lines += ('',)
    new_lines += (cp_line,)
    d = d.alter(message_lines=new_lines)
  return d


def content_of(commit):
  """Calculates the content of ``commit`` such that a gnumbd-landed commit and
  the original commit will compare as equals. Returns the content as a
  git2.CommitData object.

  This strips out:
    * The parent(s)
    * The committer date
    * footers beginning with 'Cr-'
    * the '(cherry picked from ...)' line.

  Stores a cached copy of the result data on the ``commit`` instance itself.
  """
  if commit is None:
    return git2.INVALID

  if not hasattr(commit, '_cr_content'):
    d = commit.data

    d = tweak_cherry_pick(d)

    footers = infra_types.thaw(d.footers)
    for k in footers.keys():
      if k.startswith(FOOTER_PREFIX):
        footers[k] = None

    commit._cr_content = d.alter(
        parents=(),
        committer=d.committer.alter(timestamp=git2.data.NULL_TIMESTAMP),
        footers=footers)
  return commit._cr_content  # pylint: disable=W0212


def content_difference(ref_a, ref_b):
  """Returns printable difference between contents of two commits."""
  a, b = map(lambda x: content_of(x.commit).to_dict(), [ref_a, ref_b])
  diff = {}
  for k in a:
    if a[k] != b[k]:
      diff[k] = '%s != %s' % (a[k], b[k])
  return diff


def get_position(commit, _position_re=re.compile('^(.*)@{#(\d*)}$')):
  """Returns (ref, position number) for the given ``commit``.

  Extracts them from Cr-Commit-Position footer (that looks like
  refs/heads/master\@{#287136}).

  Raises:
    MalformedPositionFooter
    NoPositionData
  """
  current_pos = commit.data.footers.get(COMMIT_POSITION)
  if not current_pos or len(current_pos) != 1:
    raise NoPositionData(commit)

  current_pos = current_pos[0]
  m = _position_re.match(current_pos)
  if not m:
    raise MalformedPositionFooter(commit, COMMIT_POSITION, current_pos)
  parent_ref = commit.repo[m.group(1)]
  parent_num = int(m.group(2))

  return parent_ref, parent_num


def synthesize_commit(commit, new_parent, ref, clock=time):
  """Synthesizes a new Commit given ``new_parent`` and ref.

  The new commit will contain a Cr-Commit-Position footer, and possibly
  Cr-Branched-From footers (if commit is on a branch).

  The new commit's committer date will also be updated to 'time.time()', or
  the new parent's date + 1, whichever is higher. This means that within
  a branch, commit timestamps will always increase (at least from the point
  where this daemon went into service).

  Uses parent's commit position to derive new commit position.

  Args:
    commit: git2.Commit
    new_parent: git2.Commit
    ref: git2.Ref
    clock: implements .time(), used for testing determinism.

  Returns:
    synthesized commit.
  """
  repo = commit.repo
  d = commit.data

  # If commit ends with a cherrypick line, remove it, then re-parse it.
  d = tweak_cherry_pick(d)

  # Remove all Cr- footers
  sanitized_d = d.alter(
    footers=collections.OrderedDict(
      (k, None) for k in d.footers
      if k.startswith(FOOTER_PREFIX)))

  footers = collections.OrderedDict()

  # Original-ify all Cr footers
  for key, value in d.footers.iteritems():
    if key.startswith(FOOTER_PREFIX):
      orig_key = key.replace(FOOTER_PREFIX, FOOTER_PREFIX + 'Original-')
      footers[orig_key] = value

  # Generate New footers.
  footers.update(generate_footers_from_parent(new_parent, ref))

  # Ensure that every commit has a time which is at least 1 second after its
  # parent, and reset the tz to UTC.
  parent_time = new_parent.data.committer.timestamp.secs
  new_parents = [] if new_parent is git2.INVALID else [new_parent.hsh]
  new_committer = d.committer.alter(
      timestamp=git2.data.NULL_TIMESTAMP.alter(
          secs=max(int(clock.time()), parent_time + 1)))

  d = sanitized_d.alter(
      parents=new_parents,
      committer=new_committer,
      footers=footers)

  return repo.get_commit(repo.intern(d, 'commit'))


def generate_footers_from_parent(new_parent, ref):
  """Generates Cr-Commit-Position footer, and possibly Cr-Branched-From footers.

  Uses parent's footers to derive new values.

  Returns
    OrderedDict
  """
  # TODO(iannucci): See if there are any other footers we want to carry over
  # between new_parent and commit
  parent_ref, parent_num = get_position(new_parent)

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


################################################################################
# Core functionality
################################################################################

def get_new_commits(real_ref, pending_tag, pending_tip):
  """Return a list of new pending commits to process or None on an error.

  Mutates pending_tag under some circumstances, see below.

  Ideally, real_ref, pending_tag and pending_tip should look something like::

          v  pending_tag
    A  B  C  D  E  F  <- pending_tip
    A' B' C' <- master

  And this method would return [D E F].

  If this arrangement is NOT the case, then this method can error out in a
  variety of ways, depending on how the repo is mangled. The most common cases
  are::

       v  pending_tag
    A  B  C  D  E  F  <- pending_tip
    A' B' C' <- master

  AND::

       v  pending_tag
    A  B  C  D  E  F  <- pending_tip
    A' B' C' D' E' F' <- master

  In either case, pending_tag would be advanced, and the method would return
  the commits between the tag's proper position and the tip.

  Other discrepancies are errors and this method will return an empty list.

  Args:
    pending_tag (git2.Ref):
    pending_tip (git2.Ref):
    real_ref (git2.Ref):

  Returns:
    [git2.Commit] or None
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
    pending_tag.repo.fast_forward_push({pending_tag: new_tag_val})

  if not new_commits:
    LOGGER.warn('Tag was lagging for %r by %d, but no new commits are pending',
                real_ref, len(new_commits))
    return []

  return new_commits


def process_ref(real_ref, pending_tag, new_commits, push_synth_extras,
                clock=time):
  """Given a ``real_ref``, its corresponding ``pending_tag``, and a list of
  ``new_commits``, copy the ``new_commits`` to ``real_ref``, and advance
  ``pending_tag``
  to match.

  Assumes that pending_tag starts at the equivalent of real_ref, and that
  all commits in new_commits exist on pending_tag..pending_tip.

  Assumes that new_commits is not empty.

  Given::

          v  pending_tag
    A  B  C  D  E  F  <- pending_tip
    A' B' C' <- master

  This function will produce::

                   v  pending_tag
    A  B  C  D  E  F  <- pending_tip
    A' B' C' D' E' F' <- master

  Args:
    real_ref (git2.Ref):
    pending_tag (git2.Ref)
    new_commits ([git2.Commit]):
    clock: implements .time(), used for testing determinism.

  Yields:
    synthesized git2.Commit, pushes them to the remote as a side-effect.
  """
  # TODO(iannucci): use push --force-with-lease to reset pending to the real
  # ref?
  # TODO(iannucci): The ACL rejection message for the real ref should point
  # users to the pending ref.
  assert new_commits, "process_ref called with no commits to process"
  assert content_of(pending_tag.commit) == content_of(real_ref.commit)
  assert real_ref.repo is pending_tag.repo
  repo = real_ref.repo
  real_parent = real_ref.commit
  ret = []

  commit = None
  synth_commit = None

  for commit in new_commits:
    assert content_of(commit.parent) == content_of(real_parent)
    synth_commit = synthesize_commit(
        commit, real_parent, real_ref, clock)

    ret.append(synth_commit)
    real_parent = synth_commit

  logging.info('Synthesized %d commits for %r', len(ret), real_ref)
  to_push = { real_ref: synth_commit, }
  to_push.update((repo[r.ref], synth_commit) for r in push_synth_extras)
  repo.fast_forward_push(to_push)

  repo.fast_forward_push({pending_tag: commit})

  return ret


def process_repo(repo, cref, clock=time):
  """Execute a single pass over a fetched Repo.

  Will call ``process_ref`` for every branch indicated by the enabled_refglobs
  config option.

  Returns: tuple (bool success status, list of synthesized commits).
  """
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

        LOGGER.debug('Processing %r', real_ref)
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
                real_ref, pending_tag, new_commits,
                push_synth_extra.get(real_ref.ref, []), clock)
            synthesized_commits.extend(commits)
        else:
          if content_of(pending_tag.commit) != content_of(real_ref.commit):
            LOGGER.error(
                '%r and %r match, but %r\'s content doesn\'t match (diff %s)!',
                pending_tag, pending_tip, real_ref,
                content_difference(pending_tag, real_ref))
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

  Returns:
    tuple (bool success status, list of synthesized commits).
  """
  repo.fetch()
  cref.evaluate()
  return process_repo(repo, cref, clock)
