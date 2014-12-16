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


class BuildMessage(messages.Message):
  """Describes model.Build, see its docstring."""
  # Build id. Not required because BuildMessage is used in 'put' service method
  # that generates build id during build creation.
  id = messages.IntegerField(1)
  namespace = messages.StringField(2, required=True)
  parameters_json = messages.StringField(3)
  status = messages.EnumField(model.BuildStatus, 4)
  result = messages.EnumField(model.BuildResult, 5)
  failure_reason = messages.EnumField(model.FailureReason, 6)
  cancelation_reason = messages.EnumField(model.CancelationReason, 7)
  lease_duration_seconds = messages.IntegerField(
      8, variant=messages.Variant.INT32)
  lease_key = messages.IntegerField(9)
  url = messages.StringField(10)


def build_to_message(build, include_lease_key=False):
  """Converts model.Build to BuildMessage."""
  assert build
  assert build.key
  assert build.key.id()

  msg = BuildMessage(
      id=build.key.id(),
      namespace=build.namespace,
      parameters_json=json.dumps(build.parameters or {}, sort_keys=True),
      status=build.status,
      result=build.result,
      cancelation_reason=build.cancelation_reason,
      failure_reason=build.failure_reason,
      lease_key=build.lease_key if include_lease_key else None,
      url=build.url,
  )
  if build.lease_expiration_date is not None:
    lease_duration = build.lease_expiration_date - utils.utcnow()
    msg.lease_duration_seconds=max(0, int(lease_duration.total_seconds()))
  return msg


def id_resource_container(body_message_class=message_types.VoidMessage):
  return endpoints.ResourceContainer(
      body_message_class,
      id=messages.IntegerField(1, required=True),
  )


def convert_service_errors(fn):
  """Decorates a function, converts service errors to endpoint exceptions."""
  @functools.wraps(fn)
  def decorated(*args, **kwargs):
    try:
      return fn(*args, **kwargs)
    except service.BuildNotFoundError:
      raise endpoints.NotFoundException()
    except (service.InvalidInputError, service.InvalidBuildStateError) as ex:
      raise endpoints.BadRequestException(ex.message)
  return decorated


def parse_json(json_data, param_name):
  if not json_data:
    return None
  try:
    return json.loads(json_data)
  except ValueError as ex:
    raise endpoints.BadRequestException(
        'Could not parse %s: %s' % (param_name, ex))


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

  @auth.endpoints_method(
      id_resource_container(), BuildMessage,
      path='builds/{id}', http_method='GET')
  @convert_service_errors
  def get(self, request):
    """Returns a build by id."""
    build = self.service.get(request.id)
    if build is None:
      raise endpoints.NotFoundException()
    return build_to_message(build)

  ###################################  PUT  ####################################

  @auth.endpoints_method(
      BuildMessage, BuildMessage,
      path='builds', http_method='PUT')
  @convert_service_errors
  def put(self, request):
    """Creates a new build."""
    if request.id:
      raise endpoints.BadRequestException('Build id must not be specified')
    if not request.namespace:
      raise endpoints.BadRequestException('Build namespace not specified')

    build = self.service.add(
        namespace=request.namespace,
        parameters=parse_json(request.parameters_json, 'parameters_json'),
        lease_duration=datetime.timedelta(
            seconds=request.lease_duration_seconds or 0),
    )
    return build_to_message(build, include_lease_key=True)

  ###################################  PEEK  ###################################

  PEEK_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      namespace=messages.StringField(1, repeated=True),
      max_builds=messages.IntegerField(
          2, variant=messages.Variant.INT32, default=10),
  )

  class PeekResponseMessage(messages.Message):
    builds = messages.MessageField(BuildMessage, 1, repeated=True)

  @auth.endpoints_method(
      PEEK_REQUEST_RESOURCE_CONTAINER, PeekResponseMessage,
      path='peek', http_method='GET')
  @convert_service_errors
  def peek(self, request):
    """Returns available builds."""
    assert isinstance(request.namespace, list)
    if not request.namespace:
      raise endpoints.BadRequestException('Namespace not specified')
    builds = self.service.peek(
        request.namespace,
        max_builds=request.max_builds)
    return self.PeekResponseMessage(builds=map(build_to_message, builds))

  ##################################  LEASE  ###################################

  class LeaseRequestBodyMessage(messages.Message):
    duration_seconds = messages.IntegerField(
        1, variant=messages.Variant.INT32, required=True)

  class LeaseResponseMessage(messages.Message):
    success = messages.BooleanField(1, required=True)
    build = messages.MessageField(BuildMessage, 2)

  @auth.endpoints_method(
      id_resource_container(LeaseRequestBodyMessage), LeaseResponseMessage,
      path='builds/{id}/lease', http_method='POST')
  @convert_service_errors
  def lease(self, request):
    """Leases a build."""
    success, build = self.service.lease(
        request.id,
        duration=datetime.timedelta(seconds=request.duration_seconds or 0),
    )
    if not success:
      return self.LeaseResponseMessage(success=False)

    assert build.lease_key is not None
    return self.LeaseResponseMessage(
        success=True,
        build=build_to_message(build, include_lease_key=True)
    )

  #################################  STARTED  ##################################


  class StartRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    url = messages.StringField(2)

  @auth.endpoints_method(
      id_resource_container(StartRequestBodyMessage), BuildMessage,
      path='builds/{id}/start', http_method='POST')
  @convert_service_errors
  def start(self, request):
    """Marks a build as started."""
    build = self.service.start(request.id, request.lease_key, url=request.url)
    return build_to_message(build)

  #################################  HEARTBEAT  ################################

  class HeartbeatRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    lease_duration_seconds = messages.IntegerField(
        2, variant=messages.Variant.INT32, required=True)

  @auth.endpoints_method(
      id_resource_container(HeartbeatRequestBodyMessage), BuildMessage,
      path='builds/{id}/heartbeat', http_method='POST')
  @convert_service_errors
  def hearbeat(self, request):
    """Updates build lease."""
    build = self.service.heartbeat(
        request.id, request.lease_key,
        datetime.timedelta(seconds=request.lease_duration_seconds))
    return build_to_message(build)

  #################################  SUCCEED  ##################################

  class SucceedRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)

  @auth.endpoints_method(
      id_resource_container(SucceedRequestBodyMessage), BuildMessage,
      path='builds/{id}/succeed', http_method='POST')
  @convert_service_errors
  def succeed(self, request):
    """Marks a build as succeeded."""
    build = self.service.succeed(request.id, request.lease_key)
    return build_to_message(build)

  ###################################  FAIL  ###################################

  class FailRequestBodyMessage(messages.Message):
    lease_key = messages.IntegerField(1)
    failure_reason = messages.EnumField(model.FailureReason, 2)

  @auth.endpoints_method(
      id_resource_container(FailRequestBodyMessage), BuildMessage,
      path='builds/{id}/fail', http_method='POST')
  @convert_service_errors
  def fail(self, request):
    """Marks a build as failed."""
    build = self.service.fail(
        request.id, request.lease_key,
        failure_reason=request.failure_reason,
    )
    return build_to_message(build)

  ##################################  CANCEL  ##################################

  @auth.endpoints_method(
      id_resource_container(message_types.VoidMessage), BuildMessage,
      path='builds/{id}/cancel', http_method='POST')
  @convert_service_errors
  def cancel(self, request):
    """Cancels a build."""
    build = self.service.cancel(request.id)
    return build_to_message(build)
