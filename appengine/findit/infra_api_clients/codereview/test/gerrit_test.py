# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import mock
import textwrap

from testing_utils import testing

from infra_api_clients.codereview.gerrit import Gerrit
from libs import time_util
from libs.http import retry_http_client


class DummyHttpClient(retry_http_client.RetryHttpClient):

  def __init__(self):
    super(DummyHttpClient, self).__init__()
    self.responses = {}
    self.requests = []

  def SetResponse(self, url, result):
    self.responses.setdefault(url, [])
    self.responses[url] = result

  def _MakeResponse(self, response):
    """Convert a json-able object into a string as returned by gerrit."""
    return ')]}\'' + json.dumps(response)

  def _SetPostMessageResponse(self, host, change_id, response_str):
    url = 'https://%s/a/changes/%s/revisions/current/review' % (host, change_id)
    self.SetResponse(url, (200, response_str))

  def _SetSubmitRevertResponse(self, host, change_id, response):
    url = 'https://%s/a/changes/%s/submit' % (host, change_id)
    self.SetResponse(url, (200, response))

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, _, headers):  # pragma: no cover
    self.requests.append((url, None, headers))
    return self._GetResponse(url)

  def _Post(self, url, data, _, headers):
    self.requests.append((url, data, headers))
    return self._GetResponse(url)

  def _GetResponse(self, url):
    """Get the appropriate response.

    If there is one reponse for the url, return it.
    If there is no response for the url, return 404.
    """
    if url not in self.responses:
      return (404, 'Not Found')
    return self.responses[url]

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
    self.assertEqual('https://server.host.name/q/%s' % change_id,
                     self.gerrit.GetCodeReviewUrl(change_id))

  def testPostMessage(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    response_str = '{}'
    self.http_client._SetPostMessageResponse(self.server_hostname, change_id,
                                             response_str)
    # This message should not change when being urlencoded or jsonized
    message = 'FinditWasHere'
    self.assertTrue(self.gerrit.PostMessage(change_id, message))
    _url, data, _headers = self.http_client.requests[0]
    self.assertIn(message, data)

  def testPostMessageNoEmail(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    response_str = '{}'
    self.http_client._SetPostMessageResponse(self.server_hostname, change_id,
                                             response_str)
    # This message should not change when being urlencoded or jsonized
    message = 'FinditWasHere'
    self.assertTrue(self.gerrit.PostMessage(change_id, message, False))
    _url, data, _headers = self.http_client.requests[0]
    self.assertIn(message, data)

  def testAddReviewerNew(self):
    change_id = 'Iabc12345'
    response = {
        'reviewers': {
            'new@dummy.org': {
                'input': 'new@dummy.org',
                'reviewers': [{
                    'email': 'new@dummy.org'
                }]
            }
        }
    }
    self.http_client._SetPostMessageResponse(self.server_hostname, change_id,
                                             json.dumps(response))
    self.assertTrue(
        self.gerrit.AddReviewers(change_id, ['new@dummy.org'], 'message'))

  def testAddReviewerWrongformat(self):
    change_id = 'Iabc12345'
    self.assertTrue(
        self.gerrit.AddReviewers(change_id, ['old@dummy.org@d.com'], 'message'))

  def testAddReviewerExisting(self):
    change_id = 'Iabc12345'
    response = {
        'reviewers': {
            'old@dummy.org': {
                'input': 'new@dummy.org',
                'reviewers': []
            }
        }
    }
    self.http_client._SetPostMessageResponse(self.server_hostname, change_id,
                                             json.dumps(response))
    self.assertTrue(
        self.gerrit.AddReviewers(change_id, ['old@dummy.org'], 'message'))

  @mock.patch.object(logging, 'error')
  def testAddReviewerMany(self, mock_logging):
    change_id = 'Iabc12345'
    response = {
        'reviewers': {
            'new@dummy.org': {
                'input': 'new@dummy.org',
                'reviewers': [{
                    'email': 'new@dummy.org'
                }]
            },
            'newtoo@dummy.org': {
                'input': 'newtoo@dummy.org',
                'reviewers': [{
                    'email': 'newtoo@dummy.org'
                }]
            },
            'old@dummy.org': {
                'input': 'old@dummy.org',
                'reviewers': [{
                    'email': 'old@dummy.org'
                }]
            },
        }
    }
    self.http_client._SetPostMessageResponse(self.server_hostname, change_id,
                                             json.dumps(response))
    self.assertTrue(
        self.gerrit.AddReviewers(change_id, [
            'new@dummy.org', 'newtoo@dummy.org', 'old@dummy.org',
            'new@dummy.org@d.com'
        ], 'message'))
    mock_logging.assert_has_called_with('Reviewer\'s email is in wrong format: '
                                        'new@dummy.org@d.com')

  def testAddReviewerFailure(self):
    change_id = 'Iabc12345'
    self.assertFalse(self.gerrit.AddReviewers(change_id, ['new@dummy.org']))

  def testGetClInfoCQCommit(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    with mock.patch.object(
        self.gerrit,
        '_Get',
        return_value={
            'change_id':
                'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7',
            'status':
                'MERGED',
            'owner': {
                'email': 'abc@chromium.org'
            },
            'submitted':
                '2017-03-24 01:07:39.000000000',
            'reviewers': {
                'REVIEWER': [{
                    'email': 'one@chromium.org'
                }, {
                    'email': 'commit-bot@chromium.org'
                }, {
                    'email': 'two@chromium.org'
                }, {
                    'email': 'three@chromium.org'
                }],
                'CC': [{
                    'email': 'four@chromium.org'
                }]
            },
            'messages': [{
                'author': {
                    'email': 'two@chromium.org'
                },
                'date': '2017-03-24 00:58:25.000000000',
                'message': 'Patch Set 3: Commit-Queue+2',
                '_revision_number': 3
            }],
            'current_revision':
                '4bd07b5148508d3d100d9d4eafb9f4d233d7fa15',
            'revisions': {
                '4bd07b5148508d3d100d9d4eafb9f4d233d7fa15': {
                    '_number': 3,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org'
                        },
                        'message': 'some message'
                    }
                }
            },
            'subject':
                'subject'
        }):
      cl_info = self.gerrit.GetClDetails(change_id)
    self.assertNotEqual(cl_info.commit_attempts.values()[0].last_cq_timestamp,
                        cl_info.commits[0].timestamp)

  def testGetClInfoManualCommit(self):
    change_id = 'I7ecd56d7d0c3fef90cfe998a29b948c5032980e4'
    with mock.patch.object(
        self.gerrit,
        '_Get',
        return_value={
            'change_id': 'I7ecd56d7d0c3fef90cfe998a29b948c5032980e4',
            'status': 'MERGED',
            'owner': {
                'email': 'abc@chromium.org'
            },
            'submitted': '2017-03-08 04:43:30.000000000',
            'reviewers': {
                'REVIEWER': [
                    {
                        'email': 'one@chromium.org'
                    },
                    {
                        'email': 'two@chromium.org'
                    },
                    {
                        'email': 'three@chromium.org'
                    },
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
                        },
                        'message': 'some message'
                    }
                }
            },
            'subject': 'subject'
        }):
      cl_info = self.gerrit.GetClDetails(change_id)
    self.assertEqual(cl_info.commit_attempts.values()[0].last_cq_timestamp,
                     cl_info.commits[0].timestamp)

  def testGetClInfoRevertedCommit(self):
    change_id = 'I4303e1b7166aaab873587a3fda0ec907d3d8ace0'
    with mock.patch.object(
        self.gerrit,
        '_Get',
        side_effect=[{
            'change_id':
                'I4303e1b7166aaab873587a3fda0ec907d3d8ace0',
            'status':
                'MERGED',
            'owner': {
                'email': 'abc@chromium.org'
            },
            'submitted':
                '2017-02-27 18:56:54.000000000',
            '_number':
                446905,
            'reviewers': {
                'REVIEWER': [{
                    'email': 'one@chromium.org'
                }, {
                    'email': 'commit-bot@chromium.org'
                }, {
                    'email': 'two@chromium.org'
                }],
                'CC': []
            },
            'messages': [{
                'id': 'b7d6785c324297ec4f1e6b2de34cf83f4c58e87c',
                'author': {
                    'email': 'one@chromium.org'
                },
                'date': '2017-02-27 18:47:15.000000000',
                'message': 'Patch Set 1: Commit-Queue+2',
                '_revision_number': 1
            }, {
                'id': 'b9e04aec4bffed0284c1f53cc5a9c88818807368',
                'tag': 'autogenerated:gerrit:revert',
                'author': {
                    'email': 'one@chromium.org'
                },
                'date': '2017-02-27 19:04:51.000000000',
                'message': 'Created a revert of this change as '
                           'If02ca1cd494579d6bb92a157bf1819e3689cd6b1',
                '_revision_number': 2
            }],
            'current_revision':
                'edda1046ce724695004242e943f59f5e1b2d00ff',
            'revisions': {
                'edda1046ce724695004242e943f59f5e1b2d00ff': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org',
                        },
                        'message': 'cl title\n\nsome description\n\n'
                                   'NOAUTOREVERT= True\n\nChange-Id: '
                                   'someid\nReviewed-on: cl_url\nCommit-Queue: '
                                   'owner\nReviewed-by: reviewers\n\n'
                                   'BUGS : 12345, 67890'
                    },
                }
            },
            'subject':
                'subject'
        }, {
            'change_id':
                'If02ca1cd494579d6bb92a157bf1819e3689cd6b1',
            'status':
                'MERGED',
            'submitted':
                '2017-02-27 19:05:03.000000000',
            'owner': {
                'email': 'abc@chromium.org'
            },
            '_number':
                446788,
            'reviewers': {
                'REVIEWER': [{
                    'email': 'one@chromium.org',
                }, {
                    'email': 'commit-bot@chromium.org',
                }, {
                    'email': 'two@chromium.org',
                }]
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
            'current_revision':
                'bd1db4534d7dc3f3f9c693ca0ac3e67caf484824',
            'revisions': {
                'bd1db4534d7dc3f3f9c693ca0ac3e67caf484824': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org',
                            'date': '2017-02-27 19:05:03.000000000',
                            'tz': 0
                        },
                        'message': 'cl title\n\nsome description\n\n'
                                   'NOAUTOREVERT=TRUE\n\nChange-Id: '
                                   'someid\nReviewed-on: cl_url\nCommit-Queue: '
                                   'owner\nReviewed-by: reviewers\n\n'
                                   'BUG: 123455'
                    },
                }
            },
            'subject':
                'subject'
        }]):
      cl_info = self.gerrit.GetClDetails(change_id)
    self.assertEqual(cl_info.serialize(), {
        'server_hostname':
            'server.host.name',
        'auto_revert_off':
            True,
        'owner_email':
            'abc@chromium.org',
        'reviewers': [
            'one@chromium.org', 'commit-bot@chromium.org', 'two@chromium.org'
        ],
        'closed':
            True,
        'commits': [{
            'patchset_id': 2,
            'timestamp': '2017-02-27 18:56:54 UTC',
            'revision': 'edda1046ce724695004242e943f59f5e1b2d00ff'
        }],
        'cc': [],
        'subject':
            'subject',
        'description':
            'cl title\n\nsome description\n\n'
            'NOAUTOREVERT= True\n\nChange-Id: '
            'someid\nReviewed-on: cl_url\nCommit-Queue: '
            'owner\nReviewed-by: reviewers\n\n'
            'BUGS : 12345, 67890',
        'change_id':
            'I4303e1b7166aaab873587a3fda0ec907d3d8ace0',
        'reverts': [{
            'patchset_id': 2,
            'reverting_user_email': 'one@chromium.org',
            'timestamp': '2017-02-27 19:04:51 UTC',
            'reverting_cl': {
                'server_hostname':
                    'server.host.name',
                'auto_revert_off':
                    True,
                'owner_email':
                    'abc@chromium.org',
                'reviewers': [
                    'one@chromium.org', 'commit-bot@chromium.org',
                    'two@chromium.org'
                ],
                'closed':
                    True,
                'commits': [{
                    'patchset_id': 2,
                    'timestamp': '2017-02-27 19:05:03 UTC',
                    'revision': 'bd1db4534d7dc3f3f9c693ca0ac3e67caf484824'
                }],
                'cc': [],
                'subject':
                    'subject',
                'description':
                    'cl title\n\nsome description\n\n'
                    'NOAUTOREVERT=TRUE\n\nChange-Id: '
                    'someid\nReviewed-on: cl_url\n'
                    'Commit-Queue: '
                    'owner\nReviewed-by: reviewers\n\n'
                    'BUG: 123455',
                'change_id':
                    'If02ca1cd494579d6bb92a157bf1819e3689cd6b1',
                'reverts': [],
                'commit_attempts': [{
                    'patchset_id': 1,
                    'timestamp': '2017-02-27 19:04:53 UTC',
                    'committing_user_email': 'one@chromium.org'
                }]
            }
        }],
        'commit_attempts': [{
            'patchset_id': 1,
            'timestamp': '2017-02-27 18:47:15 UTC',
            'committing_user_email': 'one@chromium.org'
        }]
    })

  def testCreateRevertSuccessful(self):
    change_id = 'I123456'

    reverting_change_id = 'I987654'
    response = self.http_client._MakeResponse({
        'change_id': reverting_change_id
    })
    url = 'https://%s/a/changes/%s/revert' % (self.server_hostname, change_id)
    self.http_client.SetResponse(url, (200, response))

    with mock.patch.object(
        self.gerrit, '_GenerateRevertCLDescription', return_value='Reason'):
      self.assertEqual(reverting_change_id,
                       self.gerrit.CreateRevert('Reason', change_id))

  def testCreateRevertFailure(self):
    change_id = 'I123456'
    with mock.patch.object(
        self.gerrit, '_GenerateRevertCLDescription', return_value='Reason'):
      self.assertFalse(self.gerrit.CreateRevert('Reason', change_id))

  def testRequestAddsAuthenticationPrefix(self):
    self.gerrit._AuthenticatedRequest(['changes', '123'])
    url, _payload, _headers = self.http_client.requests[0]
    self.assertEqual('https://server.host.name/a/changes/123', url)

  def testRequestKeepsAuthenticationPrefix(self):
    self.gerrit._AuthenticatedRequest(['a', 'changes', '123'])
    url, _payload, _headers = self.http_client.requests[0]
    self.assertEqual('https://server.host.name/a/changes/123', url)

  @mock.patch.object(
      time_util,
      'GetUTCNow',
      return_value=datetime.datetime(2017, 2, 27, 20, 0, 0))
  def testGenerateRevertCLDescriptionBypassCQ(self, _):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    reason = 'Reason'

    original_cl_description = textwrap.dedent("""
    cl title

    some description

    NOAUTOREVERT= True
    BUGS : 12345, 67890
    Cq-Include-Trybots: m1.b1:m2.b2
    Change-Id: someid
    Reviewed-on: cl_url
    Commit-Queue: owner
    Reviewed-by: reviewers
    """).strip()

    expected_description = textwrap.dedent("""
    Revert "cl title"

    This reverts commit edda1046ce724695004242e943f59f5e1b2d00ff.

    Reason for revert:
    Reason

    Original change's description:
    > cl title
    > 
    > some description
    > 
    > NOAUTOREVERT= True
    > BUGS : 12345, 67890
    > Cq-Include-Trybots: m1.b1:m2.b2
    > Change-Id: someid
    > Reviewed-on: cl_url
    > Commit-Queue: owner
    > Reviewed-by: reviewers

    No-Presubmit: true
    No-Tree-Checks: true
    No-Try: true
    BUGS : 12345, 67890
    Cq-Include-Trybots: m1.b1:m2.b2
    """).strip()

    with mock.patch.object(
        self.gerrit,
        '_Get',
        return_value={
            'change_id':
                'I4303e1b7166aaab873587a3fda0ec907d3d8ace0',
            'status':
                'MERGED',
            'owner': {
                'email': 'abc@chromium.org'
            },
            'submitted':
                '2017-02-27 18:56:54.000000000',
            '_number':
                446905,
            'reviewers': {
                'REVIEWER': [{
                    'email': 'one@chromium.org'
                }, {
                    'email': 'commit-bot@chromium.org'
                }, {
                    'email': 'two@chromium.org'
                }],
                'CC': []
            },
            'messages': [{
                'id': 'b7d6785c324297ec4f1e6b2de34cf83f4c58e87c',
                'author': {
                    'email': 'one@chromium.org'
                },
                'date': '2017-02-27 18:47:15.000000000',
                'message': 'Patch Set 1: Commit-Queue+2',
                '_revision_number': 1
            }],
            'current_revision':
                'edda1046ce724695004242e943f59f5e1b2d00ff',
            'revisions': {
                'edda1046ce724695004242e943f59f5e1b2d00ff': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org',
                        },
                        'message': original_cl_description
                    },
                }
            },
            'subject':
                'cl title'
        }):

      self.assertEqual(expected_description,
                       self.gerrit._GenerateRevertCLDescription(
                           change_id, reason))

  @mock.patch.object(
      time_util,
      'GetUTCNow',
      return_value=datetime.datetime(2017, 6, 1, 1, 0, 0))
  def testGenerateRevertCLDescription(self, _):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    reason = 'Reason'

    original_cl_description = textwrap.dedent("""
    cl title

    some description

    NOAUTOREVERT= True
    BUGS : 12345, 67890
    Cq-Include-Trybots: m1.b1:m2.b2
    Change-Id: someid
    Reviewed-on: cl_url
    Commit-Queue: owner
    Reviewed-by: reviewers
    """).strip()

    expected_description = textwrap.dedent("""
    Revert "cl title"

    This reverts commit edda1046ce724695004242e943f59f5e1b2d00ff.

    Reason for revert:
    Reason

    Original change's description:
    > cl title
    > 
    > some description
    > 
    > NOAUTOREVERT= True
    > BUGS : 12345, 67890
    > Cq-Include-Trybots: m1.b1:m2.b2
    > Change-Id: someid
    > Reviewed-on: cl_url
    > Commit-Queue: owner
    > Reviewed-by: reviewers

    # Not skipping CQ checks because original CL landed > 1 day ago.

    BUGS : 12345, 67890
    Cq-Include-Trybots: m1.b1:m2.b2
    """).strip()

    with mock.patch.object(
        self.gerrit,
        '_Get',
        return_value={
            'change_id':
                'I4303e1b7166aaab873587a3fda0ec907d3d8ace0',
            'status':
                'MERGED',
            'owner': {
                'email': 'abc@chromium.org'
            },
            'submitted':
                '2017-02-27 18:56:54.000000000',
            '_number':
                446905,
            'reviewers': {
                'REVIEWER': [{
                    'email': 'one@chromium.org'
                }, {
                    'email': 'commit-bot@chromium.org'
                }, {
                    'email': 'two@chromium.org'
                }],
                'CC': []
            },
            'messages': [{
                'id': 'b7d6785c324297ec4f1e6b2de34cf83f4c58e87c',
                'author': {
                    'email': 'one@chromium.org'
                },
                'date': '2017-02-27 18:47:15.000000000',
                'message': 'Patch Set 1: Commit-Queue+2',
                '_revision_number': 1
            }],
            'current_revision':
                'edda1046ce724695004242e943f59f5e1b2d00ff',
            'revisions': {
                'edda1046ce724695004242e943f59f5e1b2d00ff': {
                    '_number': 2,
                    'commit': {
                        'committer': {
                            'email': 'commit-bot@chromium.org',
                        },
                        'message': original_cl_description
                    },
                }
            },
            'subject':
                'cl title'
        }):

      self.assertEqual(expected_description,
                       self.gerrit._GenerateRevertCLDescription(
                           change_id, reason))

  def testGetBugLine(self):
    expected_results = {
        'message': '',
        'BUG: 24343\n': 'BUG: 24343\n',
        'Bug: 23234\n': 'Bug: 23234\n',
        'issue: 34254\n': 'issue: 34254\n'
    }

    for k, v in expected_results.iteritems():
      self.assertEqual(v, self.gerrit._GetBugLine(k))

  def testGetCQTryBotLine(self):
    expected_results = {
        'message':
            '',
        'cq-include-trybots: m1.b1:m2.b2\n':
            'cq-include-trybots: m1.b1:m2.b2\n',
        'CQ_INCLUDE_TRYBOTS= m1.b1:m2.b2 \n':
            'CQ_INCLUDE_TRYBOTS= m1.b1:m2.b2\n',
        'Cq_Include_Trybots= m1.b1:m2.b2\n':
            'Cq_Include_Trybots= m1.b1:m2.b2\n'
    }
    for k, v in expected_results.iteritems():
      self.assertEqual(v, self.gerrit._GetCQTryBotLine(k))

  @mock.patch.object(
      time_util,
      'GetUTCNow',
      return_value=datetime.datetime(2017, 2, 7, 1, 0, 0))
  def testGetCQFlagsOrExplanationWithinOneDay(self, _):
    time = datetime.datetime(2017, 2, 7, 0, 0, 0)
    self.assertEqual('No-Presubmit: true\nNo-Tree-Checks: true\nNo-Try: true\n',
                     self.gerrit._GetCQFlagsOrExplanation(time))

  def testSubmitRevert(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    response = self.http_client._MakeResponse({'change_id': change_id})
    self.http_client._SetSubmitRevertResponse(self.server_hostname, change_id,
                                              response)
    self.assertTrue(self.gerrit.SubmitRevert(change_id))

  def testGetChangeIdFromReviewUrl(self):
    change_id = 'I40bc1e744806f2c4aadf0ce6609aaa61b4019fa7'
    url = 'https://server.host.name/q/%s' % change_id
    self.assertEqual(change_id, self.gerrit.GetChangeIdFromReviewUrl(url))

  def testGet(self):
    path_parts = ['changes', '12345', 'detail']

    with mock.patch.object(
        self.gerrit, '_HandleResponse', return_value='return_value'):
      self.assertEqual(self.gerrit._Get(path_parts), 'return_value')
