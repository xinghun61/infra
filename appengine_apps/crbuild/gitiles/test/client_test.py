# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from gitiles import GitilesClient
from gitiles.client import parse_time
from test import CrBuildTestCase


class GitilesClientTestCase(CrBuildTestCase):
  def test_get_commit(self):
    commit_url = ('https://chromium.googlesource.com/a/project/+/'
                  '404d1697dca23824bc1130061a5bd2be4e073922?format=json')
    commit_response = """)]}'
    {
      "commit": "404d1697dca23824bc1130061a5bd2be4e073922",
      "tree": "3cfb41e1c6c37e61c3eccfab2395752298a5743c",
      "parents": [
        "4087678c002d57e1148f21da5e00867df9a7d973"
      ],
      "author": {
        "name": "John Doe",
        "email": "john.doe@chromium.org",
        "time": "Tue Apr 29 14:07:58 2014 -0700"
      },
      "committer": {
        "name": "John Doe",
        "email": "john.doe@chromium.org",
        "time": "Tue Apr 29 14:07:58 2014 -0700"
      },
      "message": "Subject\\n\\nBody",
      "tree_diff": [
        {
          "type": "modify",
          "old_id": "f23dec7da271f7e9d8c55a35f32f6971b7ce486d",
          "old_mode": 33188,
          "old_path": "codereview.settings",
          "new_id": "0bdbda926c49aa3cc4b7248bc22cc261abff5f94",
          "new_mode": 33188,
          "new_path": "codereview.settings"
        },
        {
          "type": "add",
          "old_id": "0000000000000000000000000000000000000000",
          "old_mode": 0,
          "old_path": "/dev/null",
          "new_id": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
          "new_mode": 33188,
          "new_path": "x"
        }
      ]
    }"""
    with self.mock_urlfetch() as urlfetch_mock:
      urlfetch_mock.register_handler(commit_url, commit_response)

    client = GitilesClient('chromium.googlesource.com')
    commit = client.get_commit('project',
                               '404d1697dca23824bc1130061a5bd2be4e073922')
    self.assertIsNotNone(commit)
    self.assertEqual(commit.sha, '404d1697dca23824bc1130061a5bd2be4e073922')
    self.assertEqual(commit.committer.name, 'John Doe')
    self.assertEqual(commit.committer.email, 'john.doe@chromium.org')
    self.assertEqual(commit.author.name, 'John Doe')
    self.assertEqual(commit.author.email, 'john.doe@chromium.org')

  def test_parse_time(self):
    # TODO(pgervais, crbug.com/433514) Test the case where there's a timezone.
    time_str = 'Fri Nov 07 17:09:03 2014'
    expected = datetime(2014, 11, 07, 17, 9, 3)
    actual = parse_time(time_str)
    self.assertEqual(expected, actual)
