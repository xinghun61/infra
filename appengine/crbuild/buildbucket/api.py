# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import functools
import json

from components import auth
from components import utils
from protorpc import messages
from protorpc import message_types
from protorpc import remote
import endpoints

from . import model
from . import service


class ErrorReason(messages.Enum):
  LEASE_EXPIRED = 1
  CANNOT_LEASE_BUILD = 2
  BUILD_NOT_FOUND = 3
  INVALID_INPUT = 4
  INVALID_BUILD_STATE = 5
  BUILD_IS_COMPLETED = 6


ERROR_REASON_MAP = {
    service.BuildNotFoundError: ErrorReason.BUILD_NOT_FOUND,
    service.LeaseExpiredError: ErrorReason.LEASE_EXPIRED,
    service.InvalidInputError: ErrorReason.INVALID_INPUT,
    service.InvalidBuildStateError: ErrorReason.INVALID_BUILD_STATE,
    service.BuildIsCompletedError: ErrorReason.BUILD_IS_COMPLETED,
}


class ErrorMessage(messages.Message):
  reason = messages.EnumField(ErrorReason, 1, required=True)
  message = messages.StringField(2, required=True)


class BuildMessage(messages.Message):
  """Describes model.Build, see its docstring."""
  id = messages.IntegerField(1, required=True)
  namespace = messages.StringField(2, required=True)
  tags = messages.StringField(3, repeated=True)
  parameters_json = messages.StringField(4)
  status = messages.EnumField(model.BuildStatus, 5)
  result = messages.EnumField(model.BuildResult, 6)
  result_details_json = messages.StringField(7)
  failure_reason = messages.EnumField(model.FailureReason, 8)
  cancelation_reason = messages.EnumField(model.CancelationReason, 9)
  lease_expiration_ts = messages.IntegerField(10)
  lease_key = messages.IntegerField(11)
  url = messages.StringField(12)


class BuildResponseMessage(messages.Message):
  build = messages.MessageField(BuildMessage, 1)
  error = messages.MessageField(ErrorMessage, 2)


def build_to_message(build, include_lease_key=False):
  """Converts model.Build to BuildMessage."""
  assert build
  assert build.key
  assert build.key.id()

  msg = BuildMessage(
      id=build.key.id(),
      namespace=build.namespace,
      tags=build.tags,
      parameters_json=json.dumps(build.parameters or {}, sort_keys=True),
      status=build.status,
      result=build.result,
      result_details_json=json.dumps(build.result_details),
      cancelation_reason=build.cancelation_reason,
      failure_reason=build.failure_reason,
      lease_key=build.lease_key if include_lease_key else None,
      url=build.url,
  )
  if build.lease_expiration_date is not None:
    msg.lease_expiration_ts = utils.datetime_to_timestamp(
        build.lease_expiration_date)
  return msg


def build_to_response_message(build, include_lease_key=False):
  return BuildResponseMessage(build=build_to_message(build, include_lease_key))


def id_resource_container(body_message_class=message_types.VoidMessage):
  return endpoints.ResourceContainer(
      body_message_class,
      id=messages.IntegerField(1, required=True),
  )


def buildbucket_api_method(
    request_message_class, response_message_class, **kwargs):
  """Extends auth.endpoints_method by converting service errors."""
  assert hasattr(response_message_class, 'error')

  endpoints_decorator = auth.endpoints_method(
      request_message_class, response_message_class, **kwargs)

  def decorator(fn):
    @functools.wraps(fn)
    def decorated(*args, **kwargs):
      try:
        return fn(*args, **kwargs)
      except service.Error as ex:
        return response_message_class(error=ErrorMessage(
            reason=ERROR_REASON_MAP[type(ex)],
            message=ex.message,
        ))
    return endpoints_decorator(decorated)
  return decorator


def parse_json(json_data, param_name):
  if not json_data:
    return None
  try:
    return json.loads(json_data)
  except ValueError as ex:
    raise service.InvalidInputError('Could not parse %s: %s' % (param_name, ex))


def parse_datetime(timestamp):
  if timestamp is None:
    return None
  try:
    return utils.timestamp_to_datetime(timestamp)
  except OverflowError:
    raise service.InvalidInputError(
        'Could not parse timestamp: %s' % timestamp)


@auth.endpoints_api(
    name='buildbucket', version='v1',
    title='Build Bucket Service')
class BuildBucketApi(remote.Service):
  """API for scheduling builds."""
  _service = None
  # Handy to mock.
  service_factory = service.BuildBucketService

  @property
  def service(self):
    if not self._service:  # pragma: no branch
      self._service = self.service_factory()
    return self._service

  ###################################  GET  ####################################

  @buildbucket_api_method(
      id_resource_container(), BuildResponseMessage,
      path='builds/{id}', http_method='GET')
  def get(self, request):
    """Returns a build by id."""
    build = self.service.get(request.id)
    if build is None:
      raise service.BuildNotFoundError()
    return build_to_response_message(build)

  ###################################  PUT  ####################################

  class PutRequestMessage(messages.Message):
    namespace = messages.StringField(1, required=True)
    tags = messages.StringField(2, repeated=True)
    parameters_json = messages.StringField(3)
    lease_expiration_ts = messages.IntegerField(4)

  @buildbucket_api_method(
      PutRequestMessage, BuildResponseMessage,
      path='builds', http_method='PUT')
  def put(self, request):
    """Creates a new build."""
    if not request.namespace:
      raise service.InvalidInputError('Build namespace not specified')

    build = self.service.add(
        namespace=request.namespace,
        tags=request.tags,
        parameters=parse_json(request.parameters_json, 'parameters_json'),
        lease_expiration_date=parse_datetime(request.lease_expiration_ts),
    )
    return build_to_response_message(build, include_lease_key=True)

  ##################################  SEARCH   #################################

  SEARCH_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      start_cursor=messages.StringField(1),
      # All specified tags must be present in a build.
      tag=messages.StringField(2, repeated=True),
      max_builds=messages.IntegerField(3, variant=messages.Variant.INT32),
  )

  class SearchResponseMessage(messages.Message):
    builds = messages.MessageField(BuildMessage, 1, repeated=True)
    next_cursor = messages.StringField(2)
    error = messages.MessageField(ErrorMessage, 3)

  @buildbucket_api_method(
      SEARCH_REQUEST_RESOURCE_CONTAINER, SearchResponseMessage,
      path='search', http_method='GET')
  def search(self, request):
    """Searches for builds.

    Currently only search by tag(s) is supported. Tags must contain ":".
    """
    assert isinstance(request.tag, list)
    builds, next_cursor = self.service.search_by_tags(
        request.tag,
        max_builds=request.max_builds,
        start_cursor=request.start_cursor)
    return self.SearchResponseMessage(
        builds=map(build_to_message, builds),
        next_cursor=next_cursor,
    )

  ###################################  PEEK  ###################################

  PEEK_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      namespace=messages.StringField(1, repeated=True),
      max_builds=messages.IntegerField(2, variant=messages.Variant.INT32),
      start_cursor=messages.StringField(3),
  )

  @buildbucket_api_method(
      PEEK_REQUEST_RESOURCE_CONTAINER, SearchResponseMessage,
      path='peek', http_method='GET')
  def peek(self, request):
    """Returns available builds."""
    assert isinstance(request.namespace, list)
    if not request.namespace:
      raise service.InvalidInputError('Build namespace not specified')

    builds, next_cursor = self.service.peek(
        request.namespace,
        max_builds=request.max_builds,
        start_cursor=request.start_cursor,
    )
    return self.SearchResponseMessage(
        builds=map(build_to_message, builds),
        next_cursor=next_cursor)

  ##################################  LEASE  ###################################

  class LeaseRequestBodyMessage(messages.Message):
    lease_expiration_ts = messages.IntegerField(1)

  @buildbucket_api_method(
      id_resource_container(LeaseRequestBodyMessage), BuildResponseMessage,
      path='builds/{id}/lease', http_method='POST')
  def lease(self, request):
    """Leases a build.

    Response may contain an error.
    """
    success, build = self.service.lease(
        request.id,
        lease_expiration_date=parse_datetime(request.lease_expiration_ts),
    )
    if not success:
      return BuildResponseMessage(error=ErrorMessage(
          message='Could not lease build',
          reason=ErrorReason.CANNOT_LEASE_BUILD,
      ))

    assert build.lease_key is not None
    return build_to_response_message(build, include_lease_key=True)

  #################################  STARTED  ##################################

  class StartRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    url = messages.StringField(2)

  @buildbucket_api_method(
      id_resource_container(StartRequestBodyMessage), BuildResponseMessage,
      path='builds/{id}/start', http_method='POST')
  def start(self, request):
    """Marks a build as started."""
    build = self.service.start(request.id, request.lease_key, url=request.url)
    return build_to_response_message(build)

  #################################  HEARTBEAT  ################################

  class HeartbeatRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    lease_expiration_ts = messages.IntegerField(2, required=True)

  @buildbucket_api_method(
      id_resource_container(HeartbeatRequestBodyMessage), BuildResponseMessage,
      path='builds/{id}/heartbeat', http_method='POST')
  def hearbeat(self, request):
    """Updates build lease."""
    build = self.service.heartbeat(
        request.id, request.lease_key,
        parse_datetime(request.lease_expiration_ts))
    return build_to_response_message(build)

  #################################  SUCCEED  ##################################

  class SucceedRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    result_details_json = messages.StringField(2)
    url = messages.StringField(3)

  @buildbucket_api_method(
      id_resource_container(SucceedRequestBodyMessage), BuildResponseMessage,
      path='builds/{id}/succeed', http_method='POST')
  def succeed(self, request):
    """Marks a build as succeeded."""
    build = self.service.succeed(
        request.id, request.lease_key,
        result_details=parse_json(
            request.result_details_json, 'result_details_json'),
        url=request.url)
    return build_to_response_message(build)

  ###################################  FAIL  ###################################

  class FailRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    result_details_json = messages.StringField(2)
    failure_reason = messages.EnumField(model.FailureReason, 3)
    url = messages.StringField(4)

  @buildbucket_api_method(
      id_resource_container(FailRequestBodyMessage), BuildResponseMessage,
      path='builds/{id}/fail', http_method='POST')
  def fail(self, request):
    """Marks a build as failed."""
    build = self.service.fail(
        request.id, request.lease_key,
        result_details=parse_json(
            request.result_details_json, 'result_details_json'),
        failure_reason=request.failure_reason,
        url=request.url,
    )
    return build_to_response_message(build)

  ##################################  CANCEL  ##################################

  @buildbucket_api_method(
      id_resource_container(message_types.VoidMessage), BuildResponseMessage,
      path='builds/{id}/cancel', http_method='POST')
  def cancel(self, request):
    """Cancels a build."""
    build = self.service.cancel(request.id)
    return build_to_response_message(build)
