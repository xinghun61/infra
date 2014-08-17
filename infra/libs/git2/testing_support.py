# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import tempfile

from infra.libs import git2
from infra.libs.git2 import data


class GitEntry(object):
  typ  = None
  mode = None

  def intern(self, repo):
    """Makes this GitEntry exist in |repo| (written to the git CAS), and return
    the hash of the interned object.

    If this GitEntry contains other GitEntries, the implementation of intern
    should call intern on those sub-entries.
    """
    raise NotImplementedError()

  @staticmethod
  def from_spec(spec):
    """Factory to produce a GitEntry from a spec.

    A spec is either a:
      tree - {dir: spec / GitEntry} - Produces a GitTree.
      content - str - Produces a GitFile with the default mode.
      (content, mode) - (str, int) - Produces a GitFile with the specified mode.
    """
    # TODO(iannucci): Implement links, commits, etc.
    if isinstance(spec, GitEntry):
      return spec

    if isinstance(spec, dict):
      return GitTree({
        k: GitEntry.from_spec(v) for k, v in spec.iteritems()
      })
    elif isinstance(spec, str):
      return GitFile(spec)
    elif isinstance(spec, tuple):
      return GitFile(*spec)
    raise AssertionError('Do not know how to parse spec: %r' % spec)


class GitFile(GitEntry):
  typ = 'blob'

  def __init__(self, content, mode=0644):
    super(GitFile, self).__init__()
    self.content = content
    assert mode in (0644, 0664, 0755)
    self.mode = '0100%o' % mode

  def intern(self, repo):
    return repo.intern(self.content)


class GitTree(GitEntry):
  typ = 'tree'
  mode = '0040000'

  def __init__(self, entries):
    super(GitTree, self).__init__()
    assert all(
        isinstance(k, str) and isinstance(v, GitEntry)
        for k, v in entries.iteritems()
    )
    self.entries = entries

  def intern(self, repo):
    with tempfile.TemporaryFile() as tf:
      for path, entry in self.entries.iteritems():
        tf.write('%s %s %s\t%s\0' %
                 (entry.mode, entry.typ, entry.intern(repo), path))
      tf.seek(0)
      return repo.run('mktree', '-z', stdin=tf).strip()


class TestRef(git2.Ref):
  """A testing version of git2.Ref."""

  def synthesize_commit(self, *args, **kwargs):
    """Like TestRepo.synthesize_commit, but also updates this Ref to point at
    the synthesized commit, and uses the current value of the ref as the parent.
    """
    commit = self.repo.synthesize_commit(self.commit, *args, **kwargs)
    self.update_to(commit)
    return commit


class TestClock(object):
  def __init__(self):
    self._time = 1402589336

  def time(self):
    self._time += 10
    return self._time


class TestRepo(git2.Repo):
  """A testing version of git2.Repo, which adds a couple useful methods:

    __init__          - initialize without a remote
    synthesize_commit - allow the synthesis of new commits in the repo
    snap              - Get a dict representation of the state of the refs in
                        the repo.
  """

  def __init__(self, short_name, clock, mirror_of=None):
    """
    Args:
      short_name - a testing name for this repo
      clock      - a TestClock instance, for synthesizing deterministic commits
      mirror_of  - a url to mirror, or None to create an empty bare Repo
    """
    super(TestRepo, self).__init__(mirror_of or 'local test repo')
    self._short_name = short_name
    self.repos_dir = tempfile.tempdir

    if mirror_of is None:
      # Normally _repo_path is set by the reify() method, but since we're
      # making an empty bare Repo in this mode, we set it so that reify()
      # doesn't attempt to clone from the url (which is set to the bogus
      # 'local test repo' string).
      self._repo_path = tempfile.mkdtemp(suffix='.git')
      self.run('init', '--bare')

    self._clock = clock

  def __getitem__(self, refstr):
    return TestRef(self, refstr)

  def snap(self, include_committer=False, include_config=False):
    """Take a snapshot of the history of all refs in this repo, as a dict.

    Args:
      include_committer - Include a line for the committer.
      include_config - Include the config ref(s). These are refs with the
        word 'config' in them.
    """
    ret = {}
    if include_committer:
      fmt = '%H%x00committer %cn <%ce> %ci%n%n%B%x00%x00'
    else:
      fmt = '%H%x00%B%x00%x00'
    for ref in (r.ref for r in self.refglob('*')):
      if 'config' in ref and not include_config:
        continue
      log = self.run('log', ref, '--format=%s' % fmt)
      ret[ref] = collections.OrderedDict(
          (commit, message.splitlines())
          for commit, message in (
              r.split('\0') for r in log.split('\0\0\n') if r)
      )
    return ret

  DEFAULT_TREE = object()
  def synthesize_commit(self, parent, message, tree=DEFAULT_TREE,
                        footers=None):
    """Synthesize and add a new commit object to the repo.

    Args:
      parent - a Commit object, or INVALID
      message - the message of the commit
      tree - a GitEntry-style spec for a tree, or a GitTree object. Defaults
        to a commit with a file named 'file' whose contents is 'contents'.
      footers - a dictionary-like listing of {footer_name: [values]}
    """
    if tree is TestRepo.DEFAULT_TREE:
      tree = {'file': 'contents'}
    tree = GitEntry.from_spec(tree)
    assert isinstance(tree, GitTree)
    tree = tree.intern(self)

    parents = [parent.hsh] if parent is not git2.INVALID else []

    timestamp = data.CommitTimestamp(self._clock.time(), '+', 8, 0)
    user = data.CommitUser('Test User', 'test_user@example.com', timestamp)

    return self.get_commit(self.intern(data.CommitData(
        tree, parents, user, user, (), message.splitlines(),
        data.CommitData.merge_lines([], footers or {})
    ), 'commit'))

  def __repr__(self):
    return 'TestRepo(%r)' % self._short_name
