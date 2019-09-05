# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for MonorailServicer."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import mock
import mox

from components.prpc import server
from components.prpc import codes
from components.prpc import context
from google.appengine.ext import testbed
from google.protobuf import json_format

import settings
from api import monorail_servicer
from framework import authdata
from framework import exceptions
from framework import monorailcontext
from framework import permissions
from framework import ratelimiter
from framework import xsrf
from services import cachemanager_svc
from services import config_svc
from services import service_manager
from services import features_svc
from testing import fake
from testing import testing_helpers


class MonorailServicerFunctionsTest(unittest.TestCase):

  def testConvertPRPCStatusToHTTPStatus(self):
    """We can convert pRPC status codes to http codes for monitoring."""
    prpc_context = context.ServicerContext()

    prpc_context.set_code(codes.StatusCode.OK)
    self.assertEqual(
        200, monorail_servicer.ConvertPRPCStatusToHTTPStatus(prpc_context))

    prpc_context.set_code(codes.StatusCode.INVALID_ARGUMENT)
    self.assertEqual(
        400, monorail_servicer.ConvertPRPCStatusToHTTPStatus(prpc_context))

    prpc_context.set_code(codes.StatusCode.PERMISSION_DENIED)
    self.assertEqual(
        403, monorail_servicer.ConvertPRPCStatusToHTTPStatus(prpc_context))

    prpc_context.set_code(codes.StatusCode.NOT_FOUND)
    self.assertEqual(
        404, monorail_servicer.ConvertPRPCStatusToHTTPStatus(prpc_context))

    prpc_context.set_code(codes.StatusCode.INTERNAL)
    self.assertEqual(
        500, monorail_servicer.ConvertPRPCStatusToHTTPStatus(prpc_context))


class UpdateSomethingRequest(testing_helpers.Blank):
  """A fake request that would do a write."""
  pass


class ListSomethingRequest(testing_helpers.Blank):
  """A fake request that would do a read."""
  pass


class TestableServicer(monorail_servicer.MonorailServicer):
  """Fake servicer class."""

  def __init__(self, services):
    super(TestableServicer, self).__init__(services)
    self.was_called = False
    self.seen_mc = None
    self.seen_request = None

  @monorail_servicer.PRPCMethod
  def CalcSomething(self, mc, request):
    """Raise the test exception, or return what we got for verification."""
    self.was_called = True
    self.seen_mc = mc
    self.seen_request = request
    assert mc
    assert request
    if request.exc_class:
      raise request.exc_class()
    else:
      return 'fake response proto'


class MonorailServicerTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_user_stub()

    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        cache_manager=fake.CacheManager())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111])
    self.user = self.services.user.TestAddUser('nonmember@example.com', 222)
    self.svcr = TestableServicer(self.services)
    self.token = xsrf.GenerateToken(222, xsrf.XHR_SERVLET_PATH)
    self.request = UpdateSomethingRequest(exc_class=None)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)
    self.auth = authdata.AuthData(user_id=222, email='nonmember@example.com')

    self.oauth_patcher = mock.patch(
        'google.appengine.api.oauth.get_current_user')
    self.mock_oauth_gcu = self.oauth_patcher.start()
    self.mock_oauth_gcu.return_value = None

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    self.testbed.deactivate()

  def SetUpRecordMonitoringStats(self):
    self.mox.StubOutWithMock(json_format, 'MessageToJson')
    json_format.MessageToJson(self.request).AndReturn('json of request')
    json_format.MessageToJson('fake response proto').AndReturn(
        'json of response')
    self.mox.ReplayAll()

  def testRun_SiteWide_Normal(self):
    """Calling the handler through the decorator."""
    self.SetUpRecordMonitoringStats()
    # pylint: disable=unexpected-keyword-arg
    response = self.svcr.CalcSomething(
        self.request, self.prpc_context, cnxn=self.cnxn, auth=self.auth)
    self.assertIsNone(self.svcr.seen_mc.cnxn)  # Because of CleanUp().
    self.assertEqual(self.auth, self.svcr.seen_mc.auth)
    self.assertIn(permissions.CREATE_HOTLIST.lower(),
                  self.svcr.seen_mc.perms.perm_names)
    self.assertNotIn(permissions.ADMINISTER_SITE.lower(),
                     self.svcr.seen_mc.perms.perm_names)
    self.assertEqual(self.request, self.svcr.seen_request)
    self.assertEqual('fake response proto', response)
    self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)

  def testRun_BaseChecksFail(self):
    """If we reject the request, give PERMISSION_DENIED."""
    self.auth.user_pb.banned = 'Spammer'
    self.SetUpRecordMonitoringStats()
    # pylint: disable=unexpected-keyword-arg
    self.svcr.CalcSomething(
        self.request, self.prpc_context, cnxn=self.cnxn, auth=self.auth)
    self.assertFalse(self.svcr.was_called)
    self.assertEqual(
        codes.StatusCode.PERMISSION_DENIED, self.prpc_context._code)

  def testRun_DistributedInvalidation(self):
    """The Run method must call DoDistributedInvalidation()."""
    self.SetUpRecordMonitoringStats()
    # pylint: disable=unexpected-keyword-arg
    self.svcr.CalcSomething(
        self.request, self.prpc_context, cnxn=self.cnxn, auth=self.auth)
    self.assertIsNotNone(self.services.cache_manager.last_call)

  def testRun_HandlerErrorResponse(self):
    """An expected exception in the method causes an error status."""
    self.SetUpRecordMonitoringStats()
    # pylint: disable=attribute-defined-outside-init
    self.request.exc_class = exceptions.NoSuchUserException
    # pylint: disable=unexpected-keyword-arg
    response = self.svcr.CalcSomething(
        self.request, self.prpc_context, cnxn=self.cnxn, auth=self.auth)
    self.assertTrue(self.svcr.was_called)
    self.assertIsNone(self.svcr.seen_mc.cnxn)  # Because of CleanUp().
    self.assertEqual(self.auth, self.svcr.seen_mc.auth)
    self.assertEqual(self.request, self.svcr.seen_request)
    self.assertIsNone(response)
    self.assertEqual(codes.StatusCode.NOT_FOUND, self.prpc_context._code)

  def testRun_HandlerProgrammingError(self):
    """An unexception in the handler method is re-raised."""
    self.SetUpRecordMonitoringStats()
    # pylint: disable=attribute-defined-outside-init
    self.request.exc_class = NotImplementedError
    self.assertRaises(
        NotImplementedError,
        self.svcr.CalcSomething,
        self.request, self.prpc_context, cnxn=self.cnxn, auth=self.auth)
    self.assertTrue(self.svcr.was_called)
    self.assertIsNone(self.svcr.seen_mc.cnxn)  # Because of CleanUp().

  def testGetRequester_Cookie(self):
    """We get the email address of the signed in user using cookie auth."""
    metadata = {}
    # Signed out.
    self.assertIsNone(self.svcr.GetRequester(metadata))

    # Signed in with cookie auth.
    self.testbed.setup_env(user_email='user@example.com', overwrite=True)
    self.assertEqual('user@example.com',
                     self.svcr.GetRequester(metadata))

  def testGetRequester_Oauth(self):
    """We get the email address of the signed in user using oauth."""
    metadata = {}
    # Signed out.
    self.assertIsNone(self.svcr.GetRequester(metadata))

    # Signed in with oauth.
    self.mock_oauth_gcu.return_value = testing_helpers.Blank(
        email=lambda: 'robot@example.com')
    self.assertEqual('robot@example.com',
                     self.svcr.GetRequester(metadata))

  def testGetRequester_TestAccountOnAppspot(self):
    """Specifying test_account is ignore on deployed server."""
    # pylint: disable=attribute-defined-outside-init
    metadata = {'x-test-account': 'test@example.com'}
    with self.assertRaises(exceptions.InputException):
      self.svcr.GetRequester(metadata)

  def testGetRequester_TestAccountOnDev(self):
    """For integration testing, we can set test_account on dev_server."""
    try:
      orig_local_mode = settings.local_mode
      settings.local_mode = True

      # pylint: disable=attribute-defined-outside-init
      metadata = {'x-test-account': 'test@example.com'}
      self.assertEqual(
          'test@example.com', self.svcr.GetRequester(metadata))

      # pylint: disable=attribute-defined-outside-init
      metadata = {'x-test-account': 'test@anythingelse.com'}
      with self.assertRaises(exceptions.InputException):
        self.svcr.GetRequester(metadata)
    finally:
      settings.local_mode = orig_local_mode

  def testAssertBaseChecks_SiteIsReadOnly_Write(self):
    """We reject writes and allow reads when site is read-only."""
    orig_read_only = settings.read_only
    try:
      settings.read_only = True
      metadata = {}
      self.assertRaises(
        permissions.PermissionException,
        self.svcr.AssertBaseChecks, None, self.request, metadata)
    finally:
      settings.read_only = orig_read_only

  def testAssertBaseChecks_SiteIsReadOnly_Read(self):
    """We reject writes and allow reads when site is read-only."""
    orig_read_only = settings.read_only
    try:
      settings.read_only = True
      mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
      metadata = {monorail_servicer.XSRF_TOKEN_HEADER: self.token}

      # Our default request is an update.
      with self.assertRaises(permissions.PermissionException):
        self.svcr.AssertBaseChecks(mc, self.request, metadata)

      # A method name starting with "List" or "Get" will run OK.
      self.request = ListSomethingRequest(exc_class=None)
      self.svcr.AssertBaseChecks(mc, self.request, metadata)
    finally:
      settings.read_only = orig_read_only

  def testAssertBaseChecks_Banned(self):
    """We currently only whitelist non-banned users."""
    self.auth.user_pb.banned = 'Spammer'
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    metadata = {}
    self.assertRaises(
        permissions.BannedUserException,
        self.svcr.AssertBaseChecks, mc, self.request, metadata)

  def testAssertBaseChecks_Anon(self):
    """We allow anonymous access, with a XSRF token generated by our app."""
    self.auth.user_id = 0
    metadata = {monorail_servicer.XSRF_TOKEN_HEADER:
                    xsrf.GenerateToken(0, xsrf.XHR_SERVLET_PATH)}
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.svcr.AssertBaseChecks(mc, self.request, metadata)

  def testAssertBaseChecks_ProjectNonmember(self):
    """We allow non-members."""
    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    metadata = {}
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.svcr.AssertBaseChecks(mc, self.request, metadata)

  def testAssertBaseChecks_ProjectMember(self):
    """We allow signed-in project members."""
    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.project.committer_ids.append(222)
    metadata = {}
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.svcr.AssertBaseChecks(mc, self.request, metadata)

  @mock.patch('google.appengine.api.oauth.get_client_id')
  def testAssertWhitelistedOrXSRF_Email(self, mock_get_client_id):
    """A requester (oauth or cookie) can be whitelisted by email."""
    # Disable special whitelisting of the default client_id while testing.
    mock_get_client_id.return_value = None
    # Take away the XSRF token.
    metadata = {monorail_servicer.XSRF_TOKEN_HEADER: ''}

    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.project.committer_ids.append(222)
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)

    # nonmember@example.com is not whitelisted.
    with self.assertRaises(xsrf.TokenIncorrect):
      self.auth.user_pb.email = 'nonmember@example.com'
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

    # This email is whitelisted in testing/api_clients.cfg.
    self.auth.user_pb.email = '123456789@developer.gserviceaccount.com'
    self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

  @mock.patch('google.appengine.api.oauth.get_client_id')
  def testAssertWhitelistedOrXSRF_Client(self, mock_get_client_id):
    """An oauth requester can be whitelisted by client ID."""
    # Take away the XSRF token.
    metadata = {monorail_servicer.XSRF_TOKEN_HEADER: ''}

    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.project.committer_ids.append(222)
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)

    # No client_id provided.
    with self.assertRaises(xsrf.TokenIncorrect):
      mock_get_client_id.return_value = None
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

    # client_id is not whitelisted.
    with self.assertRaises(xsrf.TokenIncorrect):
      mock_get_client_id.return_value = '0000000'
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

    # This client_id is whitelisted in testing/api_clients.cfg.
    mock_get_client_id.return_value = '123456789.apps.googleusercontent.com'
    self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

  @mock.patch('google.appengine.api.oauth.get_client_id')
  def testAssertWhitelistedOrXSRF_XSRFToken_Header(self, mock_get_client_id):
    """Our API is limited to our client by checking an XSRF token."""
    # Disable special whitelisting of the default client_id while testing.
    mock_get_client_id.return_value = None

    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.project.committer_ids.append(222)
    metadata = {'x-xsrf-token': self.token}
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)

    # The token set in setUp() works with self.auth.
    self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

    # Passing no token is OK in local_mode
    try:
      orig_local_mode = settings.local_mode
      settings.local_mode = True
      metadata = {'x-xsrf-token': ''}
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)
    finally:
      settings.local_mode = orig_local_mode

    # We detect a missing token.
    metadata = {'x-xsrf-token': ''}
    with self.assertRaises(xsrf.TokenIncorrect):
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

    # We detect a malformed, inappropriate, or expired token.
    metadata = {'x-xsrf-token': 'bad token'}
    with self.assertRaises(xsrf.TokenIncorrect):
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

  @mock.patch('google.appengine.api.oauth.get_client_id')
  @mock.patch('framework.xsrf.GetRoundedTime')
  def testAssertWhitelistedOrXSRF_CustomTimeout(
      self, mockGetRoundedTime, mock_get_client_id):
    """Our API is limited to our client by checking an XSRF token."""
    # Disable special whitelisting of the default client_id while testing.
    mock_get_client_id.return_value = None

    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.project.committer_ids.append(222)
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)

    # Set the token to an token created at time 1
    metadata = {monorail_servicer.XSRF_TOKEN_HEADER:
                  xsrf.GenerateToken(222, xsrf.XHR_SERVLET_PATH, 1)}

    # The token is too old and we fail to authenticate.
    mockGetRoundedTime.side_effect = lambda: 2 + xsrf.TOKEN_TIMEOUT_SEC
    with self.assertRaises(xsrf.TokenIncorrect):
      self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

    # We can specify a custom xsrf timeout.
    self.svcr.xsrf_timeout = 1 + xsrf.TOKEN_TIMEOUT_SEC
    self.svcr.AssertWhitelistedOrXSRF(mc, metadata)

  def testGetRequestProject(self):
    """We get a project specified by request field project_name."""
    # No project specified.
    self.assertIsNone(self.svcr.GetRequestProject(self.cnxn, self.request))

    # Existing project specified.
    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.assertEqual(
        self.project, self.svcr.GetRequestProject(self.cnxn, self.request))

    # Bad project specified.
    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'not-a-proj'
    self.assertIsNone(self.svcr.GetRequestProject(self.cnxn, self.request))

  def CheckExceptionStatus(self, e, expected_code):
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.prpc_context.set_code(codes.StatusCode.OK)
    processed = self.svcr.ProcessException(e, self.prpc_context, mc)
    if expected_code:
      self.assertTrue(processed)
      self.assertEqual(expected_code, self.prpc_context._code)
    else:
      self.assertFalse(processed)
      self.assertEqual(codes.StatusCode.OK, self.prpc_context._code)

  def testProcessException(self):
    """Expected exceptions are converted to pRPC codes, expected not."""
    self.CheckExceptionStatus(
        exceptions.NoSuchUserException(), codes.StatusCode.NOT_FOUND)
    self.CheckExceptionStatus(
        exceptions.NoSuchProjectException(), codes.StatusCode.NOT_FOUND)
    self.CheckExceptionStatus(
        exceptions.NoSuchIssueException(), codes.StatusCode.NOT_FOUND)
    self.CheckExceptionStatus(
        exceptions.NoSuchComponentException(), codes.StatusCode.NOT_FOUND)
    self.CheckExceptionStatus(
        permissions.BannedUserException(), codes.StatusCode.PERMISSION_DENIED)
    self.CheckExceptionStatus(
        permissions.PermissionException(), codes.StatusCode.PERMISSION_DENIED)
    self.CheckExceptionStatus(
        exceptions.GroupExistsException(), codes.StatusCode.INVALID_ARGUMENT)
    self.CheckExceptionStatus(
        exceptions.InvalidComponentNameException(),
        codes.StatusCode.INVALID_ARGUMENT)
    self.CheckExceptionStatus(
        ratelimiter.ApiRateLimitExceeded('client_id', 'email'),
        codes.StatusCode.PERMISSION_DENIED)
    self.CheckExceptionStatus(
        features_svc.HotlistAlreadyExists(), codes.StatusCode.INVALID_ARGUMENT)
    self.CheckExceptionStatus(NotImplementedError(), None)

  def testRecordMonitoringStats_RequestClassDoesNotEndInRequest(self):
    """We cope with request proto class names that do not end in 'Request'."""
    self.request = 'this is a string'
    self.SetUpRecordMonitoringStats()
    start_time = 1522559788.939511
    now = 1522569311.892738
    self.svcr.RecordMonitoringStats(
        start_time, self.request, 'fake response proto', self.prpc_context,
        now=now)
