# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import os

from testing_utils import testing

from infra_api_clients.codereview.gerrit import Gerrit
from libs.http import retry_http_client


class DummyHttpClient(retry_http_client.RetryHttpClient):

  def __init__(self):
    super(DummyHttpClient, self).__init__()
    self.responses = {}
    self.requests = []

  def SetResponse(self, url, result):
    self.responses[url] = result

  def _SetPostMessageResponse(self, host, change_id, response_str):
    url = 'https://%s/a/changes/%s/revisions/current/review' % (host, change_id)
    self.SetResponse(url, (200, response_str))

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, _, headers):  # pragma: no cover
    self.requests.append((url, None, headers))
    return self.responses.get(url, (404, 'Not Found'))

  def _Post(self, url, data, _, headers):  # pragma: no cover
    self.requests.append((url, data, headers))
    return self.responses.get(url, (404, 'Not Found'))

  def _Put(self, *_):  # pragma: no cover
    pass


class GerritTest(testing.AppengineTestCase):

  def setUp(self):
    super(GerritTest, self).setUp()
    self.http_client = DummyHttpClient()
    self.server_hostname = 'server.host.name'
    self.gerrit = Gerrit(self.server_hostname)
    self.gerrit.HTTP_CLIENT = self.http_client
    self.maxDiff = None

  def testGetCodeReviewUrl(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    self.assertEqual(
      'https://server.host.name/q/%s' % change_id,
      self.gerrit.GetCodeReviewUrl(change_id))

  def testPostMessage(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    response_str = ')]}\'\n{}'
    self.http_client._SetPostMessageResponse(
      self.server_hostname, change_id, response_str)
    # This message should not change when being urlencoded or jsonized
    message = 'FinditWasHere'
    self.assertTrue(self.gerrit.PostMessage(change_id, message))
    _url, data, _headers = self.http_client.requests[0]
    self.assertIn(message, data)

  def testGetClInfoCQCommit(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    with mock.patch.object(
        self.gerrit,
        '_Get',
        return_value={
            'change_id': 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7',
            'status': 'MERGED',
            'submitted': '2017-03-24 01:07:39.000000000',
            'reviewers': {
                'REVIEWER': [
                    {'email': 'one@chromium.org'},
                    {'email': 'commit-bot@chromium.org'},
                    {'email': 'two@chromium.org'},
                    {'email': 'three@chromium.org'}
                ],
                'CC': [{'email': 'four@chromium.org'}]
           },
            'messages': [{
                'author': {'email': 'two@chromium.org'},
                'date': '2017-03-24 00:58:25.000000000',
                'message': 'Patch Set 3: Commit-Queue+2',
                '_revision_number': 3
            }],
            'current_revision': '4bd07b5148508d3d100d9d4eafb9f4d233d7fa15',
            'revisions': {
                '4bd07b5148508d3d100d9d4eafb9f4d233d7fa15': {
                  '_number': 3,
                  'commit': {
                      'committer': {
                          'email': 'commit-bot@chromium.org'
                      }
                  }
               }
           }
        }):
      cl_info = self.gerrit.GetClDetails(change_id)
    self.assertNotEqual(
      cl_info.commit_attempts.values()[0].last_cq_timestamp,
      cl_info.commits[0].timestamp)

  def testGetClInfoManualCommit(self):
    change_id = 'I7ecd56d7d0c3fef90cfe998a29b948c5032980e4'
    with mock.patch.object(
        self.gerrit,
        '_Get',
        return_value={
            'change_id': 'I7ecd56d7d0c3fef90cfe998a29b948c5032980e4',
            'status': 'MERGED',
            'submitted': '2017-03-08 04:43:30.000000000',
            'reviewers': {
                'REVIEWER': [
                    {'email': 'one@chromium.org'},
                    {'email': 'two@chromium.org'},
                    {'email': 'three@chromium.org' },
                ],
                'CC': []
            },
            'messages': [],
            'current_revision': '9ff179a3962bf3465815d3a85ad46e1c3b4a9e27',
            'revisions': {
                '9ff179a3962bf3465815d3a85ad46e1c3b4a9e27': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                          'email': 'one@chromium.org',
                        }
                    }
                }
            }
        }):
      cl_info = self.gerrit.GetClDetails(change_id)
    self.assertEqual(
      cl_info.commit_attempts.values()[0].last_cq_timestamp,
      cl_info.commits[0].timestamp)

  def testGetClInfoRevertedCommit(self):
    change_id = 'I4303e1b7166aaab873587a3fda0ec907d3d8ace0'
    with mock.patch.object(
        self.gerrit,
        '_Get',
        side_effect=[{
            'change_id': 'I4303e1b7166aaab873587a3fda0ec907d3d8ace0',
            'status': 'MERGED',
            'submitted': '2017-02-27 18:56:54.000000000',
            '_number': 446905,
            'reviewers': {
                'REVIEWER': [
                    {'email': 'one@chromium.org'},
                    {'email': 'commit-bot@chromium.org'},
                    {'email': 'two@chromium.org'}
                ],
                'CC': []
            },
            'messages': [
                {
                    'id': 'b7d6785c324297ec4f1e6b2de34cf83f4c58e87c',
                    'author': {'email': 'one@chromium.org'},
                    'date': '2017-02-27 18:47:15.000000000',
                    'message': 'Patch Set 1: Commit-Queue+2',
                    '_revision_number': 1
                },
                {
                    'id': 'b9e04aec4bffed0284c1f53cc5a9c88818807368',
                    'tag': 'autogenerated:gerrit:revert',
                    'author': {'email': 'one@chromium.org'},
                    'date': '2017-02-27 19:04:51.000000000',
                    'message': 'Created a revert of this change as '
                               'If02ca1cd494579d6bb92a157bf1819e3689cd6b1',
                    '_revision_number': 2
                }
            ],
            'current_revision': 'edda1046ce724695004242e943f59f5e1b2d00ff',
            'revisions': {
                'edda1046ce724695004242e943f59f5e1b2d00ff': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org',
                        },
                    },
                }
            }
        }, {
            'change_id': 'If02ca1cd494579d6bb92a157bf1819e3689cd6b1',
            'status': 'MERGED',
            'submitted': '2017-02-27 19:05:03.000000000',
            '_number': 446788,
            'reviewers': {
                'REVIEWER': [
                    {
                        'email': 'one@chromium.org',

                    },
                    {
                        'email': 'commit-bot@chromium.org',

                    },
                    {
                        'email': 'two@chromium.org',

                    }
                ]
            },
            'messages': [
                {
                    'id': '30496ce351a43c0b74d812e9e40b440f5acff9d5',
                    'author': {
                        'email': 'one@chromium.org',

                    },
                    'date': '2017-02-27 19:04:53.000000000',
                    'message': 'Patch Set 1: Code-Review+1 Commit-Queue+2',
                    '_revision_number': 1
                },
            ],
            'current_revision': 'bd1db4534d7dc3f3f9c693ca0ac3e67caf484824',
            'revisions': {
                'bd1db4534d7dc3f3f9c693ca0ac3e67caf484824': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org',
                            'date': '2017-02-27 19:05:03.000000000',
                            'tz': 0
                        },
                    },
                }
            }
        }]):
      cl_info = self.gerrit.GetClDetails(change_id)
    self.assertEqual(cl_info.serialize(),{
      'server_hostname': 'server.host.name',
      'reviewers': [u'one@chromium.org',
                    u'commit-bot@chromium.org',
                    u'two@chromium.org'],
      'closed': True,
      'commits': [{'patchset_id': 2,
                    'timestamp': '2017-02-27 18:56:54 UTC',
                     'revision': u'edda1046ce724695004242e943f59f5e1b2d00ff'}],
      'cc': [],
      'change_id': 'I4303e1b7166aaab873587a3fda0ec907d3d8ace0',
      'reverts': [{'patchset_id': 2,
                   'reverting_user_email': u'one@chromium.org',
                   'timestamp': '2017-02-27 19:04:51 UTC',
                   'reverting_cl': {
                       'server_hostname': 'server.host.name',
                       'reviewers': [u'one@chromium.org',
                                     u'commit-bot@chromium.org',
                                     u'two@chromium.org'],
                       'closed': True,
                       'commits': [{
                           'patchset_id': 2,
                           'timestamp': '2017-02-27 19:05:03 UTC',
                           'revision':
                                 u'bd1db4534d7dc3f3f9c693ca0ac3e67caf484824'}],
                       'cc': [],
                       'change_id':
                             u'If02ca1cd494579d6bb92a157bf1819e3689cd6b1',
                             'reverts': [],
                             'commit_attempts': [{
                                 'patchset_id': 1,
                                 'timestamp': '2017-02-27 19:04:53 UTC',
                                 'committing_user_email':
                                     u'one@chromium.org'}]}}],
      'commit_attempts': [{'patchset_id': 1,
                           'timestamp': '2017-02-27 18:47:15 UTC',
                           'committing_user_email': u'one@chromium.org'}]})
