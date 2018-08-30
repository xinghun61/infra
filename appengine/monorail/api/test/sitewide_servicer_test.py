# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the sitewide servicer."""

import unittest

import mock
from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import sitewide_servicer
from api.api_proto import common_pb2
from api.api_proto import sitewide_pb2
from framework import monorailcontext
from framework import xsrf
from services import service_manager
from testing import fake


class SitewideServicerTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        usergroup=fake.UserGroupService(),
        user=fake.UserService())
    self.user_1 = self.services.user.TestAddUser('owner@example.com', 111L)
    self.sitewide_svcr = sitewide_servicer.SitewideServicer(
        self.services, make_rate_limiter=False)

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.sitewide_svcr, *args, **kwargs)

  @mock.patch('services.secrets_svc.GetXSRFKey')
  @mock.patch('framework.xsrf.GetRoundedTime')
  def testRefreshToken(self, mockGetRoundedTime, mockGetXSRFKey):
    """We can refresh an expired token."""
    mockGetXSRFKey.side_effect = lambda: 'fakeXSRFKey'
    # The token is at the brink of being too old
    mockGetRoundedTime.side_effect = lambda: 1 + xsrf.REFRESH_TOKEN_TIMEOUT_SEC

    token_path = 'token_path'
    token = xsrf.GenerateToken(111L, token_path, 1)

    request = sitewide_pb2.RefreshTokenRequest(
        token=token, token_path=token_path)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.sitewide_svcr.RefreshToken, mc, request)

    self.assertEqual(
        sitewide_pb2.RefreshTokenResponse(
            token='QSaKMyXhY752g7n8a34HyTo4NjQwMDE=',
            token_expires_sec=870901),
        response)

  @mock.patch('services.secrets_svc.GetXSRFKey')
  @mock.patch('framework.xsrf.GetRoundedTime')
  def testRefreshToken_InvalidToken(self, mockGetRoundedTime, mockGetXSRFKey):
    """We reject attempts to refresh an invalid token."""
    mockGetXSRFKey.side_effect = lambda: 'fakeXSRFKey'
    mockGetRoundedTime.side_effect = lambda: 123

    token_path = 'token_path'
    token = 'invalidToken'

    request = sitewide_pb2.RefreshTokenRequest(
        token=token, token_path=token_path)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(xsrf.TokenIncorrect):
      self.CallWrapped(self.sitewide_svcr.RefreshToken, mc, request)

  @mock.patch('services.secrets_svc.GetXSRFKey')
  @mock.patch('framework.xsrf.GetRoundedTime')
  def testRefreshToken_TokenTooOld(self, mockGetRoundedTime, mockGetXSRFKey):
    """We reject attempts to refresh a token that's too old."""
    mockGetXSRFKey.side_effect = lambda: 'fakeXSRFKey'
    mockGetRoundedTime.side_effect = lambda: 2 + xsrf.REFRESH_TOKEN_TIMEOUT_SEC

    token_path = 'token_path'
    token = xsrf.GenerateToken(111L, token_path, 1)

    request = sitewide_pb2.RefreshTokenRequest(
        token=token, token_path=token_path)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(xsrf.TokenIncorrect):
      self.CallWrapped(self.sitewide_svcr.RefreshToken, mc, request)

