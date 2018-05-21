# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

import functools
import logging
import sys
import time

from google.appengine.api import users
from google.protobuf import json_format
from components.prpc import codes
from components.prpc import server
from infra_libs import ts_mon

import settings
from framework import exceptions
from framework import framework_bizobj
from framework import monorailcontext
from framework import ratelimiter
from framework import permissions


def ConvertPRPCStatusToHTTPStatus(context):
  """pRPC uses internal codes 0..16, but we want to report HTTP codes."""
  return server._PRPC_TO_HTTP_STATUS.get(context._code, 500)


def PRPCMethod(func):
  @functools.wraps(func)
  def wrapper(self, request, prpc_context, cnxn=None, auth=None):
    return self.Run(
        func, request, prpc_context, cnxn=cnxn, auth=auth)

  wrapper.wrapped = func
  return wrapper


class MonorailServicer(object):
  """Abstract base class for API servicers.
  """

  def __init__(self, services, make_rate_limiter=True):
    self.services = services
    if make_rate_limiter:
      self.rate_limiter = ratelimiter.ApiRateLimiter()
    else:
      self.rate_limiter = None

  def Run(
      self, handler, request, prpc_context,
      cnxn=None, auth=None, perms=None, start_time=None, end_time=None):
    """Run a Do* method in an API context.

    Args:
      handler: API handler method to call with MonorailContext and request.
      request: API Request proto object.
      prpc_context: pRPC context object with status code.
      cnxn: Optional connection to SQL database.
      auth: AuthData passed in during testing.
      perms: PermissionSet passed in during testing.
      start_time: Int timestamp passed in during testing.
      end_time: Int timestamp passed in during testing.

    Returns:
      The response proto returned from the handler or None if that
      method raised an exception that we handle.

    Raises:
      Only programming errors should be raised as exceptions.  All
      execptions for permission checks and input validation that are
      raised in the Do* method are converted into pRPC status codes.
    """
    start_time = start_time or time.time()
    response = None
    client_id = None  # TODO(jrobbins): consider using client ID.
    requester = None
    mc = None
    try:
      requester = auth.email if auth else self.GetRequester()
      logging.info('request proto is:\n%r\n', request)
      logging.info('requester is %r', requester)

      if self.rate_limiter:
        self.rate_limiter.CheckStart(client_id, requester, start_time)
      mc = monorailcontext.MonorailContext(
          self.services, cnxn=cnxn, requester=requester, auth=auth, perms=perms)
      if not perms:
        mc.LookupLoggedInUserPerms(self.GetRequestProject(mc.cnxn, request))
      self.AssertBaseChecks(mc, request)
      response = handler(self, mc, request)

    except Exception as e:
      if not self.ProcessException(e, prpc_context):
        raise e.__class__, e, sys.exc_info()[2]
    finally:
      if mc:
        mc.CleanUp()
      if self.rate_limiter and requester:
        end_time = end_time or time.time()
        self.rate_limiter.CheckEnd(client_id, requester, end_time, start_time)
      self.RecordMonitoringStats(start_time, request, response, prpc_context)

    return response

  def GetRequester(self):
    """Return the email address of the signed in user or None."""
    # TODO(jrobbins): Add oauth support
    user = users.get_current_user()
    return user.email() if user else None

  def AssertBaseChecks(self, mc, request):
    """Reject requests that we refuse to serve."""
    # TODO(jrobbins): Add read_only check as an exception raised in sql.py.
    if (settings.read_only and
        not request.__class__.__name__.startswith(('Get', 'List'))):
      raise permissions.PermissionException(
          'This request is not allowed in read-only mode')

    if permissions.IsBanned(mc.auth.user_pb, mc.auth.user_view):
      raise permissions.BannedUserException(
          'The user %s has been banned from using this site' %
          mc.auth.email)
    # TODO(jrobbins): open the API to more than just signed in project members.
    if not settings.dev_mode:
      if not mc.auth.user_id:
        logging.info('TODO: open API to anon users')
        raise permissions.PermissionException()
      project = self.GetRequestProject(mc.cnxn, request)
      if project:
        if not framework_bizobj.UserIsInProject(
            project, mc.auth.effective_ids):
          logging.info('TODO: open API to non-project-members')
          raise permissions.PermissionException()

  def GetRequestProject(self, cnxn, request):
    """Return the Project business object that the user is viewing or None."""
    if hasattr(request, 'project_name'):
        project = self.services.project.GetProjectByName(
            cnxn, request.project_name)
        if not project:
          raise exceptions.NoSuchProjectException()
        return project
    else:
      return None

  def ProcessException(self, e, prpc_context):
    """Return True if we convert an exception to a pRPC status code."""
    logging.info(e.message)
    exc_type = type(e)
    if exc_type == exceptions.NoSuchUserException:
      prpc_context.set_code(codes.StatusCode.NOT_FOUND)
      prpc_context.set_details('The user does not exist.')
    elif exc_type == exceptions.NoSuchProjectException:
      prpc_context.set_code(codes.StatusCode.NOT_FOUND)
      prpc_context.set_details('The project does not exist.')
    elif exc_type == exceptions.NoSuchIssueException:
      prpc_context.set_code(codes.StatusCode.NOT_FOUND)
      prpc_context.set_details('The issue does not exist.')
    elif exc_type == exceptions.NoSuchComponentException:
      prpc_context.set_code(codes.StatusCode.NOT_FOUND)
      prpc_context.set_details('The component does not exist.')
    elif exc_type == permissions.BannedUserException:
      prpc_context.set_code(codes.StatusCode.PERMISSION_DENIED)
      prpc_context.set_details('The requesting user has been banned.')
    elif exc_type == permissions.PermissionException:
      prpc_context.set_code(codes.StatusCode.PERMISSION_DENIED)
      prpc_context.set_details('Permission denied.')
    elif exc_type == exceptions.GroupExistsException:
      prpc_context.set_code(codes.StatusCode.INVALID_ARGUMENT)
      prpc_context.set_details('The user group already exists.')
    elif exc_type == exceptions.InvalidComponentNameException:
      prpc_context.set_code(codes.StatusCode.INVALID_ARGUMENT)
      prpc_context.set_details('That component name is invalid.')
    # TODO(jrobbins): Increment and enforce action limits.
    elif exc_type == ratelimiter.ApiRateLimitExceeded:
      prpc_context.set_code(codes.StatusCode.PERMISSION_DENIED)
      prpc_context.set_details('The requester has exceeded API quotas limit.')
    else:
      return False  # Re-raise any exception from programming errors.
    return True  # It if was one of the cases above, don't reraise.

  def RecordMonitoringStats(
      self, start_time, request, response, prpc_context, now=None):
    """Record monitoring info about this request."""
    now = now or time.time()
    elapsed_ms = int((now - start_time) * 1000)
    method_name = request.__class__.__name__
    if method_name.endswith('Request'):
      method_name = method_name[:-len('Request')]
    method_identifier = 'monorail.' + method_name
    fields = {
        # pRPC uses its own statuses, but we report HTTP status codes.
        'status': ConvertPRPCStatusToHTTPStatus(prpc_context),
        # Use the api name, not the request path, to prevent an
        # explosion in possible field values.
        'name': method_identifier,
        'is_robot': False,
        }

    ts_mon.common.http_metrics.server_durations.add(
        elapsed_ms, fields=fields)
    ts_mon.common.http_metrics.server_response_status.increment(
        fields=fields)
    ts_mon.common.http_metrics.server_request_bytes.add(
        len(json_format.MessageToJson(request)), fields=fields)
    response_size = 0
    if response:
      response_size = len(json_format.MessageToJson(response))
      ts_mon.common.http_metrics.server_response_bytes.add(
          response_size, fields=fields)
