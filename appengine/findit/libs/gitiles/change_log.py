# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from libs.gitiles.diff import ChangeType


# TODO(wrengr): it'd be better to have a class hierarchy here, so we can
# avoid playing around with None, and so the change_type can be stored
# once (in the class itself; rather than once per instance).
# TODO(http://crbug/644476): better name for this class; i.e., without
# the extraneous \"Info\" at the very least.
# TODO(http://crbug.com/659346): coverage tests for the smart constructors.
class FileChangeInfo(namedtuple('FileChangeInfo',
    ['change_type', 'old_path', 'new_path'])):
  """Represents a file change (add/delete/modify/rename/copy/etc)."""
  __slots__ = ()

  @classmethod
  def Modify(cls, path): # pragma: no cover
    return cls(ChangeType.MODIFY, path, path)

  @classmethod
  def Add(cls, path): # pragma: no cover
    # Stay the same as gitile.
    return cls(ChangeType.ADD, None, path)

  @classmethod
  def Delete(cls, path): # pragma: no cover
    return cls(ChangeType.DELETE, path, None)

  @classmethod
  def Rename(cls, old_path, new_path): # pragma: no cover
    return cls(ChangeType.RENAME, old_path, new_path)

  @classmethod
  def Copy(cls, old_path, new_path): # pragma: no cover
    return cls(ChangeType.COPY, old_path, new_path)

  @classmethod
  def FromDict(cls, info):
    return cls(info['change_type'].lower(), info['old_path'], info['new_path'])

  def ToDict(self):
    return {
        'change_type': self.change_type,
        'old_path': self.old_path,
        'new_path': self.new_path
    }

  @property
  def changed_path(self):
    """Returns the changed path to check when analyzing component or project.

    Except for delete change type, the changed path means the new path after
    change, for delete type, it is the old path.
    """
    # TODO(crbug.com/685884): use component of new path as default. RENAME might
    # need to return two (old path new path may have different components)
    if self.change_type == ChangeType.DELETE:
      return self.old_path

    return self.new_path


class Contributor(namedtuple('Contributor', ['name', 'email', 'time'])):
  """A generalization of the "author" and "committer" in Git's terminology."""
  __slots__ = ()


class ChangeLog(namedtuple('ChangeLog',
    ['author', 'committer', 'revision', 'commit_position', 'message',
     'touched_files', 'commit_url', 'code_review_url', 'reverted_revision',
     'review_server_host', 'review_change_id'])):
  """Represents the change log of a revision."""
  __slots__ = ()

  def __new__(cls, author, committer, revision, commit_position, message,
              touched_files, commit_url, code_review_url=None,
              reverted_revision=None, review_server_host=None,
              review_change_id=None):
    return super(cls, ChangeLog).__new__(
        cls, author, committer, revision, commit_position, message,
        touched_files, commit_url, code_review_url, reverted_revision,
        review_server_host, review_change_id)

  def ToDict(self):
    """Returns the change log as a JSON object."""
    json_data = {
        'author': {
            'name': self.author.name,
            'email': self.author.email,
            'time': self.author.time,
        },
        'committer': {
            'name': self.committer.name,
            'email': self.committer.email,
            'time': self.committer.time,
        },
        'revision': self.revision,
        'commit_position': self.commit_position,
        'touched_files': [],
        'message': self.message,
        'commit_url': self.commit_url,
        'code_review_url': self.code_review_url,
        'reverted_revision': self.reverted_revision,
        'review_server_host': self.review_server_host,
        'review_change_id': self.review_change_id
    }
    for touched_file in self.touched_files:
      json_data['touched_files'].append(touched_file.ToDict())
    return json_data

  @staticmethod
  def FromDict(info):
    """Returns a ChangeLog instance represented by the given JSON info."""
    touched_files = []
    for touched_file_info in info['touched_files']:
      if isinstance(touched_file_info, dict):
        touched_file_info = FileChangeInfo.FromDict(touched_file_info)
      if not isinstance(touched_file_info, FileChangeInfo): # pragma: no cover
        raise TypeError("expected FileChangeInfo but got %s"
            % touched_file_info.__class__.__name__)
      touched_files.append(touched_file_info)

    return ChangeLog(
        Contributor(info['author']['name'], info['author']['email'],
                    info['author']['time']),
        Contributor(info['committer']['name'], info['committer']['email'],
                    info['committer']['time']),
        info['revision'], info['commit_position'], info['message'],
        touched_files, info['commit_url'], info['code_review_url'],
        info['reverted_revision'], info.get('review_server_host'),
        info.get('review_change_id')
    )
