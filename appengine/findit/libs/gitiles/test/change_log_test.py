# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.gitiles.change_log import FileChangeInfo, ChangeLog


class ChangeLogTest(unittest.TestCase):

  def testFileChangeinfo(self):
    filechange_dict = {'change_type': 'copy', 'old_path': 'a', 'new_path': 'b'}
    filechange_info = FileChangeInfo.FromDict(filechange_dict)
    self.assertEqual(filechange_dict, filechange_info.ToDict())

  def testFileChangeinfoChangedPathProperty(self):
    """Test ``changed_file`` property of ``FileChangeInfo``."""
    modified_file = FileChangeInfo.Modify('a.cc')
    self.assertEqual(modified_file.changed_path, 'a.cc')

    added_file = FileChangeInfo.Modify('a.cc')
    self.assertEqual(added_file.changed_path, 'a.cc')

    copied_file = FileChangeInfo.Copy('old.cc', 'new.cc')
    self.assertEqual(copied_file.changed_path, 'new.cc')

    deleted_file = FileChangeInfo.Delete('old.cc')
    self.assertEqual(deleted_file.changed_path, 'old.cc')

  def testChangeLog(self):
    change_log_dict = {
        'author': {
            'name': 'a',
            'email': 'b@email.com',
            'time': '2014-08-13 00:53:12',
        },
        'committer': {
            'name': 'c',
            'email': 'd@email.com',
            'time': '2014-08-14 00:53:12',
        },
        'revision':
            'aaaa',
        'commit_position':
            1111,
        'touched_files': [{
            'change_type': 'copy',
            'old_path': 'old_file',
            'new_path': 'new_file'
        }, {
            'change_type': 'modify',
            'old_path': 'file',
            'new_path': 'file'
        }],
        'message':
            'blabla...',
        'commit_url':
            'https://chromium.googlesource.com/chromium/src/+/git_hash',
        'code_review_url':
            'https://codereview.chromium.org/2222',
        'reverted_revision':
            '8d4a4fa6s18raf3re12tg6r',
        'review_server_host':
            'codereview.chromium.org',
        'review_change_id':
            '2222',
    }

    change_log = ChangeLog.FromDict(change_log_dict)
    self.assertEqual(change_log_dict, change_log.ToDict())
