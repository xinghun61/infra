# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class FileChangeInfo(object):
  """Represents a file change (add/delete/modify/rename/copy/etc)."""
  def __init__(self, change_type, old_path, new_path):
    self.change_type = change_type
    self.old_path = old_path
    self.new_path = new_path

  def ToDict(self):
    return {
        'change_type': self.change_type,
        'old_path': self.old_path,
        'new_path': self.new_path
    }

  @staticmethod
  def FromDict(info):
    return FileChangeInfo(
        info['change_type'], info['old_path'], info['new_path'])


class ChangeLog(object):
  """Represents the change log of a revision."""

  def __init__(self, author_name, author_email, author_time, committer_name,
               committer_email, committer_time, revision, commit_position,
               message, touched_files, commit_url, code_review_url=None,
               reverted_revision=None):
    self.author_name = author_name
    self.author_email = author_email
    self.author_time = author_time
    self.committer_name = committer_name
    self.committer_email = committer_email
    self.committer_time = committer_time
    self.revision = revision
    self.commit_position = commit_position
    self.touched_files = touched_files
    self.message = message
    self.commit_url = commit_url
    self.code_review_url = code_review_url
    self.reverted_revision = reverted_revision

  def ToDict(self):
    """Returns the change log as a Json object."""
    json_data = {
      'author_name': self.author_name,
      'author_email': self.author_email,
      'author_time': self.author_time,
      'committer_name': self.committer_name,
      'committer_email': self.committer_email,
      'committer_time': self.committer_time,
      'revision': self.revision,
      'commit_position': self.commit_position,
      'touched_files': [],
      'message': self.message,
      'commit_url': self.commit_url,
      'code_review_url': self.code_review_url,
      'reverted_revision': self.reverted_revision,
    }
    for touched_file in self.touched_files:
      json_data['touched_files'].append(touched_file.ToDict())
    return json_data

  @staticmethod
  def FromDict(info):
    """Returns a ChangeLog instance represented by the given Json info."""
    touched_files = []
    for touched_file_info in info['touched_files']:
      touched_files.append(FileChangeInfo.FromDict(touched_file_info))

    return ChangeLog(
        info['author_name'], info['author_email'], info['author_time'],
        info['committer_name'], info['committer_email'], info['committer_time'],
        info['revision'], info['commit_position'], info['message'],
        touched_files, info['commit_url'], info['code_review_url'],
        info['reverted_revision']
    )
