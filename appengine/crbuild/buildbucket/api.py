# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import functools
import json

from components import auth
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
  lease_duration_seconds = messages.IntegerField(3,
      variant=messages.Variant.INT32)
  lease_key = messages.IntegerField(4)
  status = messages.EnumField(model.BuildStatus, 5)
  parameters_json = messages.StringField(6)
  state_json = messages.StringField(7)


def build_to_message(build, include_lease_key=False):
  """Converts model.Build to BuildMessage."""
  assert build
  assert build.key
  assert build.key.id()

  lease_duration = build.available_since - datetime.datetime.utcnow()
  return BuildMessage(
      id=build.key.id(),
      namespace=build.namespace,
      status=build.status,
      parameters_json=json.dumps(build.parameters or {}, sort_keys=True),
      state_json=json.dumps(build.state or {}, sort_keys=True),
      lease_duration_seconds=max(0, int(lease_duration.total_seconds())),
      lease_key=build.lease_key if include_lease_key else None,
  )


def convert_service_errors(fn):
  """Decorates a function, converts service errors to endpoint exceptions."""
  @functools.wraps(fn)
  def decorated(*args, **kwargs):
    try:
      return fn(*args, **kwargs)
    except service.BuildNotFoundError:
      raise endpoints.NotFoundException()
    except (service.BadLeaseDurationError, service.BadLeaseKeyError,
            service.StatusIsFinalError) as ex:
      raise endpoints.BadRequestException(ex.message)
  return decorated


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

  GET_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      id=messages.IntegerField(1, required=True),
  )

  @auth.endpoints_method(
      GET_REQUEST_RESOURCE_CONTAINER, BuildMessage,
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

    parameters = None
    if request.parameters_json:  # pragma: no branch
      try:
        parameters = json.loads(request.parameters_json)
      except ValueError as ex:
        raise endpoints.BadRequestException(
            'Could not parse parameters_json: %s'% ex)

    build = self.service.add(
        namespace=request.namespace,
        parameters=parameters,
        lease_duration=datetime.timedelta(
            seconds=request.lease_duration_seconds or 0),
    )
    return build_to_message(build, include_lease_key=True)

  ###################################  PEEK  ###################################

  PEEK_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      namespace=messages.StringField(1, repeated=True),
      max_builds=messages.IntegerField(2, variant=messages.Variant.INT32,
                                       default=10),
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
    duration_seconds = messages.IntegerField(2, variant=messages.Variant.INT32,
                                             required=True)

  LEASE_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      LeaseRequestBodyMessage,
      id=messages.IntegerField(1, required=True),
  )

  class LeaseResponseMessage(messages.Message):
    success = messages.BooleanField(1, required=True)
    build = messages.MessageField(BuildMessage, 2)

  @auth.endpoints_method(
      LEASE_REQUEST_RESOURCE_CONTAINER, LeaseResponseMessage,
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

  # TODO(nodir): add "building", "completed" and "hearbeat" methods.
