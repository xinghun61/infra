# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from mock import Mock

from gerrit import GerritClient
from test import CrBuildTestCase

SHORT_CHANGE_ID = 'I7c1811882cf59c1dc55018926edb6d35295c53b8'
CHANGE_ID = 'project~master~%s' % SHORT_CHANGE_ID
REVISION = '404d1697dca23824bc1130061a5bd2be4e073922'


class GerritClientTestCase(CrBuildTestCase):
  def test_get_change(self):
    req_path = 'changes/%s?o=ALL_REVISIONS' % CHANGE_ID
    change_reponse = {
        'id': CHANGE_ID,
        'project': 'project',
        'branch': 'master',
        'hashtags': [],
        'change_id': SHORT_CHANGE_ID,
        'subject': 'My change',
        'status': 'NEW',
        'created': '2014-10-17 18:24:39.193000000',
        'updated': '2014-10-17 20:44:48.338000000',
        'mergeable': True,
        'insertions': 10,
        'deletions': 11,
        '_sortkey': '0030833c0002bff9',
        '_number': 180217,
        'owner': {
            'name': 'John Doe'
        },
        'current_revision': REVISION,
        'revisions': {
            REVISION: {
                '_number': 1,
                'fetch': {
                  'http': {
                      'url': 'https://chromium.googlesource.com/html-office',
                      'ref': 'refs/changes/80/123/1'
                  }
                }
            }
        }
    }
    client = GerritClient('chromium-review.googlesource.com')
    client._fetch = Mock(return_value=change_reponse)
    change = client.get_change(CHANGE_ID)
    client._fetch.assert_called_once_with(req_path)
    self.assertIsNotNone(change)
    self.assertEqual(change.change_id, SHORT_CHANGE_ID)
    self.assertEqual(change.branch, 'master')
    self.assertEqual(change.project, 'project')
    self.assertEqual(change.owner.name, 'John Doe')
    self.assertEqual(change.current_revision, REVISION)

    # smoke test for branch coverage
    change = client.get_change(CHANGE_ID, include_all_revisions=False,
                               include_owner_details=True)

  def test_get_nonexistent_change(self):
    client = GerritClient('chromium-review.googlesource.com')
    change = client.get_change(CHANGE_ID)
    self.assertIsNone(change)

  def test_set_review(self):
    req_path = 'changes/%s/revisions/%s/review' % (CHANGE_ID, REVISION)
    labels = {'Verified': 1 }
    client = GerritClient('chromium-review.googlesource.com')
    client._fetch = Mock(return_value={'labels': labels})
    client.set_review(CHANGE_ID, REVISION, message='Hi!', labels=labels)
    client._fetch.assert_called_with(req_path, method='POST', body={
        'message': 'Hi!',
        'labels': labels,
    })

    # Test with "notify" parameter.
    client.set_review(CHANGE_ID, REVISION, message='Hi!', labels=labels,
                      notify='all')
    client._fetch.assert_called_with(req_path, method='POST', body={
        'message': 'Hi!',
        'labels': labels,
        'notify': 'ALL',
    })

    with self.assertRaises(AssertionError):
        client.set_review(CHANGE_ID, REVISION, notify='Argh!')
