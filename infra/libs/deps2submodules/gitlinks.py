# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Builds Git tree object suitable for use in submodule mirror repo.

To build the tree, we start with a tree-ish from a specific commit from the
source repo, and add to it (1) a .gitmodules file, at top level; and (2)
gitlink objects for each of the submodule dependencies.  For each gitlink,
we add it to the tree object representing the subdirectory in which it is
to appear; but having done that, then recursively each parent subdirectory
tree has to be rebuilt (since the hash values would now be different).

We combine the rebuilding of parent subdirectory trees where possible.  For
example, with:

    third_party/WebKit
               /...
               /libphonenumber/src/phonenumbers
                                  /resources
                                  /test

we rebuild "src" and "libphonenumber" only once each, even though there are
three gitlinks.  Similarly, there are dozens of gitlinks under third_party/...
but we only rebuild that tree once as well.

In order to achieve that, we start by sorting the paths (lexicographically by
path name), so that we can process related paths together.  For each level of
subdirectory we keep track of it on a stack, and accumulate a "to do" list of
trees that we have rebuilt, that need to be added to (or replaced) in their
parents.


If this technique of cobbling together all the necessary internal Git objects
"by hand" is unfamiliar, it is worth studying the following chapter of the Git
book: https://git-scm.com/book/en/v2/Git-Internals-Git-Objects.
"""

import collections
import itertools
import posixpath


# Each item in the stack is a PendingTree object.
PendingTree = collections.namedtuple('PendingTree', 'path,to_do')


class Gitlinks(object):

  def __init__(self, repo, gitmodules_file_hash, submodules, origin_commit):
    """Instantiates the Gitlink tree builder.

    Args:
      repo: an instance of infra.libs.git2.Repo, representing the target repo
          into which the gitlinks and resultant new tree objects are to be
          built.
      gitmodules_file_hash: string containing the SHA-1 hash of the .gitmodules
          file matching the submodules to be included; the Git blob object
          representing the file is assumed to have been interned already
      submodules: a dict of path=>SubmodData, where the path is a string naming
          the file system path to a submodule, and SubmodData is a
          collections.namedtuple with fields `url` and `revision`, which are
          both strings (revision is a 40-character SHA-1 hash).
      origin_commit: string containing a Git tree-ish that may be used with
          an ls-tree command (in the target repo), representing the repo content
          before any gitlinks or the .gitmodule file have been added to it.
    """
    self._repo = repo
    self._gitmodules_file_hash = gitmodules_file_hash
    self._submodules = submodules
    self._origin_commit = origin_commit
    self._stack = [
        PendingTree('./', [_Blob(self._gitmodules_file_hash, '.gitmodules')])]


  def BuildRootTree(self):
    """Adds gitlink entries based on submodule definitions.

    Returns the SHA-1 hash of the root tree.
    """

    # Notes:
    # 1. To keep things simple, we stick an initial "./" on the beginning
    #    of all paths.  That way, there's always at least the one slash, even
    #    for a gitlink that occurs at top level, and even for directory names
    #    only one deep.
    # 2. (Sub-)directory paths stored in PendingTree objects always terminate
    #    with a trailing slash, even though after the rsplit() call we have to
    #    put it there ourselves.

    sorted_items = sorted(self._submodules.iteritems(), None, lambda (k, v): k)
    for path, data in sorted_items:
      split = ('./' + path).rsplit('/', 1)
      assert len(split) == 2
      sub_dir, _ = split
      sub_dir += '/'

      # There are three cases:
      # 1. The sub_dir is the same as top-of-stack.
      # 2. It's in a sub-directory of top-of-stack.
      # 3. Otherwise it's in a part of the tree unrelated to top-of-stack.
      top = self._stack[-1]
      if sub_dir == top.path:
        top.to_do.append(_Gitlink(data.revision, path))
      elif sub_dir.startswith(top.path):
        self._PushMulti(sub_dir, path, data)
      else:
        self._PopMismatchingSubdirs(sub_dir)
        top = self._stack[-1]
        # At this point, either case #1 or #2 is possible.
        if sub_dir == top.path:
          top.to_do.append(_Gitlink(data.revision, path))
        else:
          assert sub_dir.startswith(top.path)
          self._PushMulti(sub_dir, path, data)

    root_hash = self._PopRemainingSubdirs()
    return root_hash


  def _PushMulti(self, sub_dir, path, data):
    """Pushes common components of a sub-directory path name onto the stack.

    Saves submodule information for later: we don't yet know if there will be
    more things to add to the "tree" in which it appears.

    Args:
      path: (string) the full path name of a submodule
      sub_dir: (string) the directory name(s) of the path.  It should be a
          sub-directory of the current top-of-stack element's path.
      data: the submodule's SubmodData object
    """
    prefix = self._stack[-1].path
    assert sub_dir.startswith(prefix) and prefix.endswith('/')
    remains = sub_dir[len(prefix):len(sub_dir)-1].split('/')
    assert remains                # we have at least one path component
    for name in remains:
      prefix = prefix + name + '/'
      self._stack.append(PendingTree(prefix, []))
    self._stack[-1].to_do.append(_Gitlink(data.revision, path))


  # The following two _PopXxxxx methods are very similar, except for their loop
  # controls.  Combining them into one method would be possible, but the
  # resulting code would be so weird and complicated as to be counterproductive.

  def _PopMismatchingSubdirs(self, new_path):
    """Bakes all pending stack entries unrelated to the new path.

    Upon completion, the top-of-stack has one or more items in its
    to-do list, and its path represents a prefix of the new path.
    """

    # This loop is guaranteed to terminate, because the deepest stack element
    # has path "./" and any new_path value should start with "./"
    assert new_path.endswith('/') and self._stack[-1].to_do
    while not new_path.startswith(self._stack[-1].path):
      pending_tree = self._stack.pop()
      tree_hash = self._Bake(pending_tree)
      self._stack[-1].to_do.append(_Tree(tree_hash, pending_tree.path))


  def _PopRemainingSubdirs(self):
    """Bakes all pending stack entries.

    Called when all submodules have been processed (either already baked
    somewhere, or still pending in a to-do list in the stack).
    """
    assert self._stack                  # always non-empty upon entry
    while True:
      pending_tree = self._stack.pop()
      tree_hash = self._Bake(pending_tree)
      if self._stack:
        self._stack[-1].to_do.append(_Tree(tree_hash, pending_tree.path))
      else:
        return tree_hash


  def _Bake(self, pending_tree):
    """Builds a Git tree object with added content (somewhere, recursively).

    Now that we know there will be no further additions to the tree at the
    given path (or any of its sub-directories), we can compute the final
    content including SHA-1 hash.

    Args:
      pending_tree: a PendingTree object representing the sub-directory to be
      built, along with the to-do list of things to be added (_Blob, _Tree,
      and/or _Gitlink objects).
    """
    def _parse(line):
      parts = line.split('\t')
      metadata, path = parts
      return (posixpath.basename(path), metadata)

    # Read the existing tree, convert it to a dict of name:metadata (after
    # stripping parent directory names).
    text = self._repo.run('ls-tree', self._origin_commit, pending_tree.path)
    entries = {k:v for (k, v) in itertools.imap(_parse, text.splitlines())}

    # Add new gitlinks and replace recomputed tree objects.
    for add in pending_tree.to_do:
      name, metadata = add.format()
      entries[name] = metadata

    # Reassemble as lines of text, for input to mktree.
    def _accumulate(lst, item):
      name, metadata = item
      lst.append('%s\t%s' % (metadata, name))
      return lst
    lines = reduce(_accumulate, entries.iteritems(), [])
    tree_hash = self._repo.run('mktree', indata='\n'.join(lines)).rstrip('\n')
    return tree_hash


class _Gitlink(object):
  def __init__(self, hsh, name):
    self._hsh = hsh
    self._name = posixpath.basename(name)

  def format(self):
    return (self._name, '160000 commit %s' % (self._hsh,))


class _Tree(object):
  def __init__(self, hsh, name):
    assert name.endswith('/')
    self._hsh = hsh
    self._name = posixpath.basename(name[:-1])

  def format(self):
    return (self._name, '040000 tree %s' % (self._hsh,))


class _Blob(object):
  def __init__(self, hsh, name):
    self._hsh = hsh
    self._name = name

  def format(self):
    return (self._name, '100644 blob %s' % (self._hsh,))
