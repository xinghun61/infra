# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.change_log import FileChangeInfo
from common.change_log import ChangeLog

class ChangeLogTest(unittest.TestCase):
  def testFileChangeinfo(self):
    filechange_dict = {
        'change_type': 'copy',
        'old_path': 'a',
        'new_path': 'b'
    }
    filechange_info = FileChangeInfo.FromDict(filechange_dict)
    self.assertEqual(filechange_dict, filechange_info.ToDict())

  def testChangeLog(self):
    change_log_dict = {
      'author_name': 'a',
      'author_email': 'b@email.com',
      'author_time': '2014-08-13 00:53:12',
      'committer_name': 'c',
      'committer_email': 'd@email.com',
      'committer_time': '2014-08-14 00:53:12',
      'revision': 'aaaa',
      'commit_position': 1111,
      'touched_files': [
          {
              'change_type': 'copy',
              'old_path': 'old_file',
              'new_path': 'new_file'
          },
          {
              'change_type': 'modify',
              'old_path': 'file',
              'new_path': 'file'
          }
      ],
      'message': 'blabla...',
      'commit_url': 'https://chromium.googlesource.com/chromium/src/+/git_hash',
      'code_review_url': 'https://codereview.chromium.org/2222',
      'reverted_revision': '8d4a4fa6s18raf3re12tg6r'
    }

    change_log = ChangeLog.FromDict(change_log_dict)
    self.assertEqual(change_log_dict, change_log.ToDict())
