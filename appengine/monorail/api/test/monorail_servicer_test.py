# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for MonorailServicer."""

import unittest

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
from services import config_svc
from services import service_manager
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
  pass


class ListSomethingRequest(testing_helpers.Blank):
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
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=789, owner_ids=[111L])
    self.user = self.services.user.TestAddUser('nonmember@example.com', 222L)
    self.svcr = TestableServicer(self.services)
    self.request = UpdateSomethingRequest(exc_class=None)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)
    self.auth = authdata.AuthData(user_id=222L, email='nonmember@example.com')

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

  def testGetRequester(self):
    """We get the email address of the signed in user."""
    self.assertIsNone(self.svcr.GetRequester())
    self.testbed.setup_env(user_email='user@example.com', overwrite=True)
    self.assertEqual('user@example.com', self.svcr.GetRequester())

  def testAssertBaseChecks_SiteIsReadOnly_Write(self):
    """We reject writes and allow reads when site is read-only."""
    orig_read_only = settings.read_only
    try:
      settings.read_only = True
      self.assertRaises(
        permissions.PermissionException,
        self.svcr.AssertBaseChecks, None, self.request)
    finally:
      settings.read_only = orig_read_only

  def testAssertBaseChecks_SiteIsReadOnly_Read(self):
    """We reject writes and allow reads when site is read-only."""
    orig_read_only = settings.read_only
    try:
      settings.read_only = True
      self.request = ListSomethingRequest(exc_class=None)
      mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
      self.svcr.AssertBaseChecks(mc, self.request)
    finally:
      settings.read_only = orig_read_only

  def testAssertBaseChecks_Banned(self):
    """We currently only whitelist non-banned users."""
    self.auth.user_pb.banned = 'Spammer'
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.assertRaises(
        permissions.BannedUserException,
        self.svcr.AssertBaseChecks, mc, self.request)

  def testAssertBaseChecks_Anon(self):
    """We currently only whitelist signed-in project members."""
    self.auth.user_id = 0
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.assertRaises(
        permissions.PermissionException,
        self.svcr.AssertBaseChecks, mc, self.request)

  def testAssertBaseChecks_Anon_Localhost(self):
    """We don't check whitelists when running locally."""
    orig_dev_mode = settings.dev_mode
    try:
      settings.dev_mode = True
      self.auth.user_id = 0
      mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
      self.svcr.AssertBaseChecks(mc, self.request)
    finally:
      settings.dev_mode = orig_dev_mode

  def testAssertBaseChecks_ProjectNonmember(self):
    """We currently only whitelist signed-in project members."""
    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.assertRaises(
        permissions.PermissionException,
        self.svcr.AssertBaseChecks, mc, self.request)

  def testAssertBaseChecks_ProjectMember(self):
    """We currently only whitelist signed-in project members."""
    # pylint: disable=attribute-defined-outside-init
    self.request.project_name = 'proj'
    self.project.committer_ids.append(222L)
    mc = monorailcontext.MonorailContext(self.services, auth=self.auth)
    self.svcr.AssertBaseChecks(mc, self.request)

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
    self.assertRaises(
        exceptions.NoSuchProjectException,
        self.svcr.GetRequestProject, self.cnxn, self.request)

  def CheckExceptionStatus(self, e, expected_code):
    self.prpc_context.set_code(codes.StatusCode.OK)
    processed = self.svcr.ProcessException(e, self.prpc_context)
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
