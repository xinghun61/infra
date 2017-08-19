# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for jsonfeed module."""

import httplib
import logging
import unittest

from google.appengine.api import app_identity

from framework import jsonfeed
from framework import servlet
from framework import xsrf
from services import service_manager
from testing import testing_helpers


class JsonFeedTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'

  def testGet(self):
    """Tests handling of GET requests."""
    feed = TestableJsonFeed()

    # all expected args are present + a bonus arg that should be ignored
    feed.mr = testing_helpers.MakeMonorailRequest(
        path='/foo/bar/wee?sna=foo', method='POST',
        params={'a': '123', 'z': 'zebra'})
    feed.get()

    self.assertEqual(True, feed.handle_request_called)
    self.assertEqual(1, len(feed.json_data))

  def testPost(self):
    """Tests handling of POST requests."""
    feed = TestableJsonFeed()
    feed.mr = testing_helpers.MakeMonorailRequest(
        path='/foo/bar/wee?sna=foo', method='POST',
        params={'a': '123', 'z': 'zebra'})

    feed.post()

    self.assertEqual(True, feed.handle_request_called)
    self.assertEqual(1, len(feed.json_data))

  def testSecurityTokenChecked_BadToken(self):
    feed = TestableJsonFeed()
    feed.mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 555})
    # Note that feed.mr has no token set.
    self.assertRaises(xsrf.TokenIncorrect, feed.get)
    self.assertRaises(xsrf.TokenIncorrect, feed.post)

    feed.mr.token = 'bad token'
    self.assertRaises(xsrf.TokenIncorrect, feed.get)
    self.assertRaises(xsrf.TokenIncorrect, feed.post)

  def testSecurityTokenChecked_HandlerDoesNotNeedToken(self):
    feed = TestableJsonFeed()
    feed.mr = testing_helpers.MakeMonorailRequest(
        user_info={'user_id': 555})
    # Note that feed.mr has no token set.
    feed.CHECK_SECURITY_TOKEN = False
    feed.get()
    feed.post()

  def testSecurityTokenChecked_AnonUserDoesNotNeedToken(self):
    feed = TestableJsonFeed()
    feed.mr = testing_helpers.MakeMonorailRequest()
    # Note that feed.mr has no token set, but also no auth.user_id.
    feed.get()
    feed.post()

  def testSameAppOnly_ExternallyAccessible(self):
    feed = TestableJsonFeed()
    feed.mr = testing_helpers.MakeMonorailRequest()
    # Note that request has no X-Appengine-Inbound-Appid set.
    feed.get()
    feed.post()

  def testSameAppOnly_InternalOnlyCalledFromSameApp(self):
    feed = TestableJsonFeed()
    feed.CHECK_SAME_APP = True
    feed.mr = testing_helpers.MakeMonorailRequest()
    app_id = app_identity.get_application_id()
    feed.mr.request.headers['X-Appengine-Inbound-Appid'] = app_id
    feed.get()
    feed.post()

  def testSameAppOnly_InternalOnlyCalledExternally(self):
    feed = TestableJsonFeed()
    feed.CHECK_SAME_APP = True
    feed.mr = testing_helpers.MakeMonorailRequest()
    # Note that request has no X-Appengine-Inbound-Appid set.
    self.assertIsNone(feed.get())
    self.assertFalse(feed.handle_request_called)
    self.assertEqual(httplib.FORBIDDEN, feed.response.status)
    self.assertIsNone(feed.post())
    self.assertFalse(feed.handle_request_called)
    self.assertEqual(httplib.FORBIDDEN, feed.response.status)

  def testSameAppOnly_InternalOnlyCalledFromWrongApp(self):
    feed = TestableJsonFeed()
    feed.CHECK_SAME_APP = True
    feed.mr = testing_helpers.MakeMonorailRequest()
    feed.mr.request.headers['X-Appengine-Inbound-Appid'] = 'wrong'
    self.assertIsNone(feed.get())
    self.assertFalse(feed.handle_request_called)
    self.assertEqual(httplib.FORBIDDEN, feed.response.status)
    self.assertIsNone(feed.post())
    self.assertFalse(feed.handle_request_called)
    self.assertEqual(httplib.FORBIDDEN, feed.response.status)


class TestableJsonFeed(jsonfeed.JsonFeed):

  def __init__(self, request=None):
    response = testing_helpers.Blank()
    super(TestableJsonFeed, self).__init__(
        request or 'req', response, services=service_manager.Services())

    self.response_data = None
    self.handle_request_called = False
    self.json_data = None

  def HandleRequest(self, mr):
    self.handle_request_called = True
    return {'a': mr.GetParam('a')}

  # The output chain is hard to double so we pass on that phase,
  # but save the response data for inspection
  def _RenderJsonResponse(self, json_data):
    self.json_data = json_data
