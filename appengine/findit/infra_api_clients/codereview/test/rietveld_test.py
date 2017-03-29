# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import os
import textwrap

from testing_utils import testing

from infra_api_clients.codereview.rietveld import Rietveld
from libs.http import retry_http_client


class DummyHttpClient(retry_http_client.RetryHttpClient):

  def __init__(self):
    super(DummyHttpClient, self).__init__()
    self.responses = {}
    self.requests = []

  def SetResponse(self, url, result):
    self.responses[url] = result

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, _, headers):
    self.requests.append((url, None, headers))
    return self.responses.get(url, (404, 'Not Found'))

  def _Post(self, url, data, _, headers):
    self.requests.append((url, data, headers))
    return self.responses.get(url, (404, 'Not Found'))

  def _Put(self, *_):  # pragma: no cover
    pass


class RietveldTest(testing.AppengineTestCase):

  def setUp(self):
    super(RietveldTest, self).setUp()
    self.http_client = DummyHttpClient()
    self.server_hostname = 'server.host.name'
    self.rietveld = Rietveld(self.server_hostname)
    self.rietveld.HTTP_CLIENT = self.http_client

  def testGetXsrfTokenSuccess(self):
    self.http_client.SetResponse('https://%s/xsrf_token' % self.server_hostname,
                                 (200, 'abc'))
    self.assertEqual('abc', self.rietveld._GetXsrfToken())
    self.assertEqual(1, len(self.http_client.requests))
    _, _, headers = self.http_client.requests[0]
    self.assertTrue('X-Requesting-XSRF-Token' in headers)

  def testGetXsrfTokenFailure(self):
    self.http_client.SetResponse('https://%s/xsrf_token' % self.server_hostname,
                                 (302, 'login'))
    self.assertIsNone(self.rietveld._GetXsrfToken())

  def testEncodeMultipartFormDataOfEmptyFormFields(self):
    content_type, body = self.rietveld._EncodeMultipartFormData({})
    self.assertIsNone(content_type)
    self.assertIsNone(body)

  def testEncodeMultipartFormData(self):
    content_type, body = self.rietveld._EncodeMultipartFormData({'a':'b'})
    expected_content_type = (
        'multipart/form-data; boundary=-F-I-N-D-I-T-M-E-S-S-A-G-E-')
    expected_body = textwrap.dedent("""
    ---F-I-N-D-I-T-M-E-S-S-A-G-E-\r
    Content-Disposition: form-data; name="a"\r
    \r
    b\r
    ---F-I-N-D-I-T-M-E-S-S-A-G-E---\r
    """)[1:]
    self.assertEqual(expected_content_type, content_type)
    self.assertEqual(expected_body, body)

  def testPostMessageSuccess(self):
    change_id = 123
    message_publish_url = 'https://%s/%s/publish' % (
        self.server_hostname, change_id)
    self.http_client.SetResponse('https://%s/xsrf_token' % self.server_hostname,
                                 (200, 'abc'))
    self.http_client.SetResponse(message_publish_url, (200, 'OK'))
    self.assertTrue(self.rietveld.PostMessage(change_id, 'message'))
    self.assertEqual(2, len(self.http_client.requests))

  def testPostMessageFailOnXsrfToken(self):
    change_id = 123
    message_publish_url = 'https://%s/%s/publish' % (
        self.server_hostname, change_id)
    self.http_client.SetResponse('https://%s/xsrf_token' % self.server_hostname,
                                 (302, 'login'))
    self.http_client.SetResponse(message_publish_url, (200, 'OK'))
    self.assertFalse(self.rietveld.PostMessage(change_id, 'message'))
    self.assertEqual(1, len(self.http_client.requests))

  def testPostMessageFailOnPublish(self):
    change_id = 123
    message_publish_url = 'https://%s/%s/publish' % (
        self.server_hostname, change_id)
    self.http_client.SetResponse('https://%s/xsrf_token' % self.server_hostname,
                                 (200, 'abc'))
    self.http_client.SetResponse(message_publish_url, (404, 'Error'))
    self.assertFalse(self.rietveld.PostMessage(change_id, 'message'))
    self.assertEqual(2, len(self.http_client.requests))

  @mock.patch.object(Rietveld, '_SendPostRequest')
  def testCreateRevertSuccess(self, mocked_SendPostRequest):
    mocked_SendPostRequest.side_effect = [(200, '1234')]
    change_id = self.rietveld.CreateRevert('reason', 1222, 20001)
    self.assertEqual('1234', change_id)
    mocked_SendPostRequest.assert_called_once_with(
        '/api/1222/20001/revert',
        {'revert_reason': 'reason', 'revert_cq': 0, 'no_redirect': 'True'})

  @mock.patch.object(Rietveld, '_SendPostRequest')
  def testCreateRevertFail(self, mocked_SendPostRequest):
    mocked_SendPostRequest.side_effect = [(404, 'error')]
    change_id = self.rietveld.CreateRevert('reason', 1222, 20001)
    self.assertIsNone(change_id)
    mocked_SendPostRequest.assert_called_once_with(
        '/api/1222/20001/revert',
        {'revert_reason': 'reason', 'revert_cq': 0, 'no_redirect': 'True'})

  @mock.patch(
      'libs.time_util.DatetimeFromString',
      lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f'))
  def testGetClDetails(self):
    rietveld_url = 'https://server.host.name'
    change_id = '123456001'
    revert_change_id = '2713613003'
    with open(os.path.join(os.path.dirname(__file__),
              'testissuedetails.json')) as f:
      response = 200, f.read()
    self.http_client.SetResponse('%s/api/%s?messages=true' %
                                 (rietveld_url, change_id), response)
    with open(os.path.join(os.path.dirname(__file__),
              'reverttestissuedetails.json')) as f:
      response = 200, f.read()
    self.http_client.SetResponse('%s/api/%s?messages=true' %
                                 (rietveld_url, revert_change_id), response)
    cl_info = self.rietveld.GetClDetails(change_id)
    self.assertEqual(cl_info.serialize(),
    {'server_hostname': 'server.host.name',
     'change_id': '123456001',
     'commits': [
         {
             'patchset_id': '100001',
             'timestamp': '2017-02-23 02:41:16 UTC',
             'revision': 'c0ffebabedeadc0dec0ffebabedeadc0dec0ffeb'
         },
         {
             'patchset_id': '120001',
             'timestamp': '2017-02-23 23:17:54 UTC',
             'revision': 'deadbeefdeadbeefc001c001c001ce120ce120aa'
         }
     ],
     'commit_attempts': [
         {
             'committing_user_email': u'author@chromium.org',
             'patchset_id': '100001',
             'timestamp': '2017-02-23 00:52:00 UTC'
         },
         {
             'committing_user_email': u'author@chromium.org',
             'patchset_id': '120001',
             'timestamp': '2017-02-23 23:17:54 UTC',
         }
     ],
     'reverts': [
         {
             'patchset_id': '100001',
             'reverting_cl': {
                 'cc': [u'chromium-reviews@chromium.org'],
                 'reviewers': [u'someone@chromium.org'],
                 'server_hostname': 'server.host.name',
                 'change_id': '2713613003',
                 'commits': [
                     {
                         'patchset_id': '20001',
                         'timestamp': '2017-02-23 23:17:54 UTC',
                         'revision': 'deadbeefdeadbeefc001c001c001ce120ce120aa'
                     }
                 ],
                 'commit_attempts': [
                     {
                         'committing_user_email': u'author@chromium.org',
                         'patchset_id': '20001',
                         'timestamp': '2017-02-23 21:24:47 UTC'
                     }
                 ],
                 'reverts': [],
                 'closed': True
             },
             'reverting_user_email': 'reviewer@chromium.org',
             'timestamp': '2017-02-23 03:09:25 UTC'
         }
     ],
     'cc': [u'chromium-reviews@chromium.org'],
     'reviewers': [u'someone@chromium.org'],
     'closed': True})

  @mock.patch(
      'libs.time_util.DatetimeFromString',
      lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f'))
  def testGetClDetailsManualCommit(self):
    rietveld_url = 'https://server.host.name'
    change_id = '123456001'
    with open(os.path.join(os.path.dirname(__file__),
              'manualtestissuedetails.json')) as f:
      response = 200, f.read()
    self.http_client.SetResponse('%s/api/%s?messages=true' %
                                 (rietveld_url, change_id), response)
    cl_info = self.rietveld.GetClDetails(change_id)

    self.assertEqual(2, len(cl_info.commits))

  @mock.patch('infra_api_clients.codereview.rietveld.Rietveld._SendPostRequest')
  def testAddReviewersNewReviewer(self, mock_send):
    mock_send.return_value = (200, 'OK')
    rietveld_url = 'https://server.host.name'
    change_id = '2713613003'
    with open(os.path.join(os.path.dirname(__file__),
                           'reverttestissuedetails.json')) as f:
      response = 200, f.read()
    self.http_client.SetResponse('%s/api/%s?messages=true' %
                                 (rietveld_url, change_id), response)
    self.rietveld.AddReviewers(change_id, ['dummy@dummy.com'])
    mock_send.assert_called_once()
    url, data = mock_send.call_args[0]
    self.assertEqual('/%s/publish' % change_id, url)
    self.assertEqual({
        'message_only': 'False',
        'no_redirect': 'True',
        'add_as_reviewer': 'False',
        'reviewers': u'someone@chromium.org,dummy@dummy.com',
        'cc': u'chromium-reviews@chromium.org',
        'commit': 'False',
        'message': '',
        'send_mail': 'True'
    }, data)

  @mock.patch('infra_api_clients.codereview.rietveld.Rietveld._SendPostRequest')
  def testAddReviewersExistingReviewer(self, mock_send):
    rietveld_url = 'https://server.host.name'
    change_id = '2713613003'
    with open(os.path.join(os.path.dirname(__file__),
                           'reverttestissuedetails.json')) as f:
      response = 200, f.read()
    self.http_client.SetResponse('%s/api/%s?messages=true' %
                                 (rietveld_url, change_id), response)
    # Should be a no-op because reviewer was already assigned in issue.
    self.rietveld.AddReviewers(change_id, ['someone@chromium.org'])
    mock_send.assert_not_called()

  def testGetCodeReviewUrl(self):
    change_id = '1234123001'
    self.assertEqual(
      'https://server.host.name/%s/' % change_id,
      self.rietveld.GetCodeReviewUrl(change_id))
