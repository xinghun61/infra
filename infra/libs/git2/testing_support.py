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

  @staticmethod
  def spec_for(repo, treeish):
    """Return a GitEntry-compatible spec from something which resolves to a
    tree.
    """
    if hasattr(treeish, 'hsh'):
      treeish = treeish.hsh
    spec = {}
    for entry in repo.run('ls-tree', '-zr', treeish).split('\0'):
      if not entry:
        continue
      metadata, path = entry.split('\t')
      mode, typ, hsh = metadata.split(' ')

      # since we did a recursive ls-tree, the only thing we should see are
      # blobs.
      assert typ == 'blob', 'Cannot handle anything but blobs and trees!'

      subspec = spec
      pieces = path.split('/')
      for subpath in pieces[:-1]:
        subspec = subspec.setdefault(subpath, {})
      subspec[pieces[-1]] = (repo.run('cat-file', 'blob', hsh),
                             int(mode[1:], 8))
    return spec

  @staticmethod
  def merge_specs(left, right):
    """Merge two specs.

    If a value in the right tree is None, it's removed if present in left.

    All conflicts are resolved in the favor of the right spec.
    """
    assert left is not None, 'left spec cannot contain None'
    if right is None:
      return right

    if type(left) != type(right):
      return right

    assert isinstance(left, dict), (
      'Do not know how to merge (%r, %r)' % (left, right))

    new_spec = {}
    old = set(left.keys())
    new = set(right.keys())

    # any keys in both are merged.
    for key in (old & new):
      merged = GitEntry.merge_specs(left[key], right[key])
      if merged is not None:
        new_spec[key] = merged

    # keys in old, but not in new are carried from the left
    for key in (old - new):
      new_spec[key] = left[key]

    # keys in new, but not in old are carried from the right
    for key in (new - old):
      new_spec[key] = right[key]

    return new_spec


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

  def make_full_tree_commit(self, *args, **kwargs):
    """Like TestRepo.make_full_tree_commit, but also updates this Ref to point
    at the synthesized commit, and uses the current value of the ref as the
    parent.
    """
    commit = self.repo.make_full_tree_commit(self.commit, *args, **kwargs)
    self.fast_forward(commit)
    return commit

  def make_commit(self, *args, **kwargs):
    """Like TestRepo.make_commit, but also updates this Ref to point at
    the synthesized commit, and uses the current value of the ref as the parent.
    """
    commit = self.repo.make_commit(self.commit, *args, **kwargs)
    self.fast_forward(commit)
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
    make_*_commit     - allow the synthesis of new commits in the repo
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
    ret = collections.OrderedDict()
    if include_committer:
      fmt = '%H%x00committer %cn <%ce> %ci%n%n%B%x00%x00'
    else:
      fmt = '%H%x00%B%x00%x00'
    for ref in sorted(r.ref for r in self.refglob('*')):
      if 'config' in ref and not include_config:
        continue
      log = self.run('log', ref, '--format=%s' % fmt)
      ret[ref] = collections.OrderedDict(
          (commit, message.splitlines())
          for commit, message in (
              r.split('\0') for r in log.split('\0\0\n') if r)
      )
    return ret

  def _synth_commit(self, parent, message, tree=None, footers=None):
    """Internal helper for make_commit and make_full_tree_commit."""
    tree = GitEntry.from_spec(tree or {})
    assert isinstance(tree, GitTree)
    tree_hash = tree.intern(self)

    parents = [parent.hsh] if parent is not git2.INVALID else []

    timestamp = data.CommitTimestamp(self._clock.time(), '+', 8, 0)
    user = data.CommitUser('Test User', 'test_user@example.com', timestamp)

    return self.get_commit(self.intern(data.CommitData(
        tree_hash, parents, user, user, (), message.splitlines(),
        data.CommitData.merge_lines([], footers or {})
    ), 'commit'))


  DEFAULT_TREE = object()
  def make_full_tree_commit(self, parent, message, tree=DEFAULT_TREE,
                            footers=None):
    """Synthesize and add a new commit object to the repo, where the tree is
    described in its entirety via a GitEntry spec.

    Args:
      parent  - a Commit object, or INVALID.
      message - the message of the commit.
      tree    - a GitEntry-style spec for a tree, or a GitTree object.
                Defaults to the tree `{'file': 'contents'}`.
      footers - a dictionary-like listing of {footer_name: [values]}.
    """
    if tree is self.DEFAULT_TREE:
      tree = {'file': 'contents'}
    return self._synth_commit(parent, message, tree=tree, footers=footers)


  def make_commit(self, parent, message, tree_diff=None, footers=None):
    """Synthesize and add a new commit object to the repo, where the tree is
    described differentially from |parent|'s tree.

    Args:
      parent    - a Commit object, or INVALID.
      message   - the message of the commit.
      tree_diff - a mergable GitEntry-style spec which will be merged into the
                  spec retrieved from |parent| as the right side using
                  GitEntry.merge_specs. If |parent| is INVALID, tree_diff is
                  taken as a full tree spec.
      footers   - a dictionary-like listing of {footer_name: [values]}.
    """
    parent_spec = {}
    if parent is not git2.INVALID:
      parent_spec = self.spec_for(parent)
    tree = GitEntry.merge_specs(parent_spec, tree_diff)
    return self._synth_commit(parent, message, tree=tree, footers=footers)


  def spec_for(self, treeish):
    return GitEntry.spec_for(self, treeish)

  def __repr__(self):
    return 'TestRepo(%r)' % self._short_name
