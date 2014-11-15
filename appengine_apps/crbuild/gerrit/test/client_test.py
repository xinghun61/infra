# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gerrit import GerritClient
from test import CrBuildTestCase


class GerritClientTestCase(CrBuildTestCase):
  def test_get_change(self):
    change_url = (
        'https://chromium-review.googlesource.com/a/changes/'
        'project~master~I7c1811882cf59c1dc55018926edb6d35295c53b8'
        '?o=ALL_REVISIONS')
    change_reponse = """)]}'
    {
      "id": "project~master~I7c1811882cf59c1dc55018926edb6d35295c53b8",
      "project": "project",
      "branch": "master",
      "hashtags": [],
      "change_id": "I7c1811882cf59c1dc55018926edb6d35295c53b8",
      "subject": "My change",
      "status": "NEW",
      "created": "2014-10-17 18:24:39.193000000",
      "updated": "2014-10-17 20:44:48.338000000",
      "mergeable": true,
      "insertions": 10,
      "deletions": 11,
      "_sortkey": "0030833c0002bff9",
      "_number": 180217,
      "owner": {
        "name": "John Doe"
      },
      "current_revision": "404d1697dca23824bc1130061a5bd2be4e073922",
      "revisions": {
        "404d1697dca23824bc1130061a5bd2be4e073922": {
          "_number": 1,
          "fetch": {
            "http": {
              "url": "https://chromium.googlesource.com/html-office",
              "ref": "refs/changes/80/123/1"
            }
          }
        }
      }
    }"""
    with self.mock_urlfetch() as urlfetch_mock:
      urlfetch_mock.register_handler(change_url, change_reponse)

    client = GerritClient('chromium-review.googlesource.com')
    gerrit_id = 'project~master~I7c1811882cf59c1dc55018926edb6d35295c53b8'
    change = client.get_change(gerrit_id)
    self.assertIsNotNone(change)
    self.assertEqual(change.change_id,
                     'I7c1811882cf59c1dc55018926edb6d35295c53b8')
    self.assertEqual(change.branch, 'master')
    self.assertEqual(change.project, 'project')
    self.assertEqual(change.owner.name, 'John Doe')
    self.assertEqual(change.current_revision,
                    '404d1697dca23824bc1130061a5bd2be4e073922')

    # smoke test for branch coverage
    change = client.get_change(gerrit_id, include_owner_details=True,
                               include_all_revisions=False)
