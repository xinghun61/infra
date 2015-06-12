# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

class Dependency(object):
  """Represents a dependency in Chrome, like blink, v8, pdfium, etc."""
  def __init__(self, path, repo_url, revision, deps_file='DEPS'):
    self.path = path
    self.repo_url = repo_url
    self.revision = revision
    self.deps_file = deps_file
    self.parent = None
    self.children = dict()

  def SetParent(self, parent):
    assert self.parent is None
    self.parent = parent
    self.parent.AddChild(self)

  def AddChild(self, child):
    self.children[child.path] = child

  def ToDict(self):
    children_dict = {}
    for path, child in self.children.iteritems():
      children_dict[path] = child.ToDict()
    return {
        'path': self.path,
        'repo_url': self.repo_url,
        'revision': self.revision,
        'deps_file': self.deps_file,
        'children': children_dict,
    }


class DependencyRoll(collections.namedtuple(
    'DependencyRoll', ('path', 'repo_url', 'old_revision', 'new_revision'))):
  """Represents a dependency roll (revision update) in chromium.

  Note: It is possible that the DEPS roll is a revert so that ``new_revision``
  is actually older than ``old_revision`` in the dependency.
  """

  def ToDict(self):
    return self._asdict()
