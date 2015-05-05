# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import functools
import json
import logging

from components import auth
from components import utils
from protorpc import messages
from protorpc import message_types
from protorpc import remote
import endpoints

import acl
import errors
import model
import service


class ErrorReason(messages.Enum):
  LEASE_EXPIRED = 1
  CANNOT_LEASE_BUILD = 2
  BUILD_NOT_FOUND = 3
  INVALID_INPUT = 4
  INVALID_BUILD_STATE = 5
  BUILD_IS_COMPLETED = 6


ERROR_REASON_MAP = {
    errors.BuildNotFoundError: ErrorReason.BUILD_NOT_FOUND,
    errors.LeaseExpiredError: ErrorReason.LEASE_EXPIRED,
    errors.InvalidInputError: ErrorReason.INVALID_INPUT,
    errors.BuildIsCompletedError: ErrorReason.BUILD_IS_COMPLETED,
}


class ErrorMessage(messages.Message):
  reason = messages.EnumField(ErrorReason, 1, required=True)
  message = messages.StringField(2, required=True)


def exception_to_error_message(ex):
  assert isinstance(ex, errors.Error)
  return ErrorMessage(
      reason=ERROR_REASON_MAP[type(ex)],
      message=ex.message,
  )


class PutRequestMessage(messages.Message):
  client_operation_id = messages.StringField(1)
  bucket = messages.StringField(2, required=True)
  tags = messages.StringField(3, repeated=True)
  parameters_json = messages.StringField(4)
  lease_expiration_ts = messages.IntegerField(5)


class BuildMessage(messages.Message):
  """Describes model.Build, see its docstring."""
  id = messages.IntegerField(1, required=True)
  bucket = messages.StringField(2, required=True)
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
  created_ts = messages.IntegerField(13)
  updated_ts = messages.IntegerField(14)
  completed_ts = messages.IntegerField(15)
  created_by = messages.StringField(16)
  status_changed_ts = messages.IntegerField(17)
  utcnow_ts = messages.IntegerField(18, required=True)


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
      bucket=build.bucket,
      tags=build.tags,
      parameters_json=json.dumps(build.parameters or {}, sort_keys=True),
      status=build.status,
      result=build.result,
      result_details_json=json.dumps(build.result_details),
      cancelation_reason=build.cancelation_reason,
      failure_reason=build.failure_reason,
      lease_key=build.lease_key if include_lease_key else None,
      url=build.url,
      created_ts=datetime_to_timestamp_safe(build.create_time),
      updated_ts=datetime_to_timestamp_safe(build.update_time),
      completed_ts=datetime_to_timestamp_safe(build.complete_time),
      created_by=build.created_by.to_bytes() if build.created_by else None,
      status_changed_ts=datetime_to_timestamp_safe(build.status_changed_time),
      utcnow_ts=datetime_to_timestamp_safe(utils.utcnow()),
  )
  if build.lease_expiration_date is not None:
    msg.lease_expiration_ts = utils.datetime_to_timestamp(
        build.lease_expiration_date)
  return msg


def build_to_response_message(build, include_lease_key=False):
  return BuildResponseMessage(build=build_to_message(build, include_lease_key))


class BucketAclMessage(messages.Message):
  class RuleMessage(messages.Message):
    role = messages.EnumField(acl.Role, 1, required=True)
    group = messages.StringField(2, required=True)

  rules = messages.MessageField(RuleMessage, 1, repeated=True)
  modified_by = messages.StringField(2)
  modified_ts = messages.IntegerField(3)


class BucketAclResponseMessage(messages.Message):
  acl = messages.MessageField(BucketAclMessage, 1)
  error = messages.MessageField(ErrorMessage, 2)


def bucket_acl_to_response_message(bucket_acl):
  response = BucketAclResponseMessage()
  if bucket_acl:
    response.acl = BucketAclMessage(
        rules=[
            BucketAclMessage.RuleMessage(
                role=rule.role,
                group=rule.group,
            ) for rule in bucket_acl.rules],
        modified_by=bucket_acl.modified_by.to_bytes(),
        modified_ts=utils.datetime_to_timestamp(bucket_acl.modified_time),
    )
  return response


def id_resource_container(body_message_class=message_types.VoidMessage):
  return endpoints.ResourceContainer(
      body_message_class,
      id=messages.IntegerField(1, required=True),
  )


def buildbucket_api_method(
    request_message_class, response_message_class, **kwargs):
  """Extends auth.endpoints_method by converting service errors."""

  endpoints_decorator = auth.endpoints_method(
      request_message_class, response_message_class, **kwargs)

  def decorator(fn):
    @functools.wraps(fn)
    def decorated(*args, **kwargs):
      try:
        return fn(*args, **kwargs)
      except errors.Error as ex:
        assert hasattr(response_message_class, 'error')
        return response_message_class(error=exception_to_error_message(ex))
    return endpoints_decorator(decorated)
  return decorator


def parse_json(json_data, param_name):
  if not json_data:
    return None
  try:
    return json.loads(json_data)
  except ValueError as ex:
    raise errors.InvalidInputError('Could not parse %s: %s' % (param_name, ex))


def parse_datetime(timestamp):
  if timestamp is None:
    return None
  try:
    return utils.timestamp_to_datetime(timestamp)
  except OverflowError:
    raise errors.InvalidInputError(
        'Could not parse timestamp: %s' % timestamp)


def datetime_to_timestamp_safe(value):
  if value is None:
    return None
  return utils.datetime_to_timestamp(value)


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
      raise errors.BuildNotFoundError()
    return build_to_response_message(build)

  ###################################  PUT  ####################################

  @buildbucket_api_method(
      PutRequestMessage, BuildResponseMessage,
      path='builds', http_method='PUT')
  def put(self, request):
    """Creates a new build."""
    build = self.service.add(
        bucket=request.bucket,
        tags=request.tags,
        parameters=parse_json(request.parameters_json, 'parameters_json'),
        lease_expiration_date=parse_datetime(request.lease_expiration_ts),
        client_operation_id=request.client_operation_id,
    )
    return build_to_response_message(build, include_lease_key=True)

  ################################  PUT_BATCH  #################################

  class PutBatchRequestMessage(messages.Message):
    builds = messages.MessageField(PutRequestMessage, 1, repeated=True)

  class PutBatchResponseMessage(messages.Message):
    class OneResult(messages.Message):
      client_operation_id = messages.StringField(1)
      build = messages.MessageField(BuildMessage, 2)
      error = messages.MessageField(ErrorMessage, 3)
    results = messages.MessageField(OneResult, 1, repeated=True)

  @buildbucket_api_method(
      PutBatchRequestMessage, PutBatchResponseMessage,
      path='builds/batch', http_method='PUT')
  def put_batch(self, request):
    """Creates builds."""
    build_futures = [
        self.service.add_async(
            bucket=put_req.bucket,
            tags=put_req.tags,
            parameters=parse_json(put_req.parameters_json, 'parameters_json'),
            lease_expiration_date=parse_datetime(put_req.lease_expiration_ts),
            client_operation_id=put_req.client_operation_id,
        )
        for put_req in request.builds
    ]

    res = self.PutBatchResponseMessage()

    def to_msg(req, build_future):
      one_res = res.OneResult(client_operation_id=req.client_operation_id)
      try:
        build = build_future.get_result()
        one_res.build = build_to_message(build, include_lease_key=True)
      except errors.Error as ex:
        one_res.error = exception_to_error_message(ex)
      return one_res

    res.results = [
        to_msg(req, build)
        for req, build in zip(request.builds, build_futures)]
    return res

  ##################################  SEARCH   #################################

  SEARCH_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      start_cursor=messages.StringField(1),
      # All specified tags must be present in a build.
      bucket=messages.StringField(2, repeated=True),
      tag=messages.StringField(3, repeated=True),
      status=messages.EnumField(model.BuildStatus, 4),
      result=messages.EnumField(model.BuildResult, 5),
      cancelation_reason=messages.EnumField(model.CancelationReason, 6),
      failure_reason=messages.EnumField(model.FailureReason, 7),
      created_by=messages.StringField(8),
      max_builds=messages.IntegerField(9, variant=messages.Variant.INT32),
  )

  class SearchResponseMessage(messages.Message):
    builds = messages.MessageField(BuildMessage, 1, repeated=True)
    next_cursor = messages.StringField(2)
    error = messages.MessageField(ErrorMessage, 3)

  @buildbucket_api_method(
      SEARCH_REQUEST_RESOURCE_CONTAINER, SearchResponseMessage,
      path='search', http_method='GET')
  def search(self, request):
    """Searches for builds."""
    assert isinstance(request.tag, list)
    builds, next_cursor = self.service.search(
        buckets=request.bucket,
        tags=request.tag,
        status=request.status,
        result=request.result,
        failure_reason=request.failure_reason,
        cancelation_reason=request.cancelation_reason,
        max_builds=request.max_builds,
        created_by=request.created_by,
        start_cursor=request.start_cursor)
    return self.SearchResponseMessage(
        builds=map(build_to_message, builds),
        next_cursor=next_cursor,
    )

  ###################################  PEEK  ###################################

  PEEK_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      bucket=messages.StringField(1, repeated=True),
      max_builds=messages.IntegerField(2, variant=messages.Variant.INT32),
      start_cursor=messages.StringField(3),
  )

  @buildbucket_api_method(
      PEEK_REQUEST_RESOURCE_CONTAINER, SearchResponseMessage,
      path='peek', http_method='GET')
  def peek(self, request):
    """Returns available builds."""
    assert isinstance(request.bucket, list)
    builds, next_cursor = self.service.peek(
        request.bucket,
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

  #################################  RESET  ####################################

  @buildbucket_api_method(
      id_resource_container(), BuildResponseMessage,
      path='builds/{id}/reset', http_method='POST')
  def reset(self, request):
    """Forcibly unleases a build and resets its state to SCHEDULED."""
    build = self.service.reset(request.id)
    return build_to_response_message(build)

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
    lease_key = messages.IntegerField(1, required=True)
    lease_expiration_ts = messages.IntegerField(2, required=True)

  @buildbucket_api_method(
      id_resource_container(HeartbeatRequestBodyMessage), BuildResponseMessage,
      path='builds/{id}/heartbeat', http_method='POST')
  def heartbeat(self, request):
    """Updates build lease."""
    build = self.service.heartbeat(
        request.id, request.lease_key,
        parse_datetime(request.lease_expiration_ts))
    return build_to_response_message(build)

  class HeartbeatBatchRequestMessage(messages.Message):
    class OneHeartbeat(messages.Message):
      build_id = messages.IntegerField(1, required=True)
      lease_key = messages.IntegerField(2, required=True)
      lease_expiration_ts = messages.IntegerField(3, required=True)
    heartbeats = messages.MessageField(OneHeartbeat, 1, repeated=True)

  class HeartbeatBatchResponseMessage(messages.Message):
    class OneHeartbeatResult(messages.Message):
      build_id = messages.IntegerField(1, required=True)
      lease_expiration_ts = messages.IntegerField(2)
      error = messages.MessageField(ErrorMessage, 3)
    results = messages.MessageField(OneHeartbeatResult, 1, repeated=True)

  @buildbucket_api_method(
      HeartbeatBatchRequestMessage, HeartbeatBatchResponseMessage,
      path='heartbeat', http_method='POST')
  def heartbeat_batch(self, request):
    """Updates multiple build leases."""
    heartbeats = [
        {
            'build_id': h.build_id,
            'lease_key': h.lease_key,
            'lease_expiration_date': parse_datetime(h.lease_expiration_ts),
        } for h in request.heartbeats
    ]

    def to_message((build_id, build, ex)):
      msg = self.HeartbeatBatchResponseMessage.OneHeartbeatResult(
          build_id=build_id)
      if build:
        msg.lease_expiration_ts = utils.datetime_to_timestamp(
            build.lease_expiration_date)
      else:
        if not isinstance(ex, errors.Error):
          logging.error(ex.message, exc_info=ex)
          raise endpoints.InternalServerErrorException(ex.message)

        assert type(ex) in ERROR_REASON_MAP
        msg.error = ErrorMessage(
            reason=ERROR_REASON_MAP[type(ex)],
            message=ex.message,
        )

      return msg

    results = self.service.heartbeat_batch(heartbeats)
    return self.HeartbeatBatchResponseMessage(results=map(to_message, results))

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
      id_resource_container(), BuildResponseMessage,
      path='builds/{id}/cancel', http_method='POST')
  def cancel(self, request):
    """Cancels a build."""
    build = self.service.cancel(request.id)
    return build_to_response_message(build)

  ###############################  CANCEL_BATCH  ###############################

  class CancelBatchRequestMessage(messages.Message):
    build_ids = messages.IntegerField(1, repeated=True)

  class CancelBatchResponseMessage(messages.Message):
    class OneResult(messages.Message):
      build_id = messages.IntegerField(1, required=True)
      build = messages.MessageField(BuildMessage, 2)
      error = messages.MessageField(ErrorMessage, 3)
    results = messages.MessageField(OneResult, 1, repeated=True)

  @buildbucket_api_method(
      CancelBatchRequestMessage, CancelBatchResponseMessage,
      path='builds/cancel', http_method='POST')
  def cancel_batch(self, request):
    """Cancels builds."""
    res = self.CancelBatchResponseMessage()
    for build_id in request.build_ids:
      one_res = res.OneResult(build_id=build_id)
      try:
        build = self.service.cancel(build_id)
        one_res.build = build_to_message(build)
      except errors.Error as ex:
        one_res.error = exception_to_error_message(ex)
      res.results.append(one_res)
    return res

  #################################  GET ACL  ##################################

  GET_ACL_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      bucket=messages.StringField(1, required=True),
  )

  @buildbucket_api_method(
      GET_ACL_REQUEST_RESOURCE_CONTAINER, BucketAclResponseMessage,
      path='bucket/{bucket}/acl', http_method='GET',
      name='acl.get')
  def get_acl(self, request):
    """Returns bucket ACL."""
    service.validate_bucket_name(request.bucket)
    bucket_acl = acl.get_acl(request.bucket)
    return bucket_acl_to_response_message(bucket_acl)

  #################################  SET ACL  ##################################

  class SetAclRequestBodyMessage(messages.Message):
    rules = messages.MessageField(
        BucketAclMessage.RuleMessage, 1, repeated=True)

  SET_ACL_REQUEST_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      SetAclRequestBodyMessage,
      bucket=messages.StringField(1, required=True),
  )

  @buildbucket_api_method(
      SET_ACL_REQUEST_RESOURCE_CONTAINER, BucketAclResponseMessage,
      path='bucket/{bucket}/acl', http_method='POST',
      name='acl.set')
  def set_acl(self, request):
    """Sets bucket ACL."""
    service.validate_bucket_name(request.bucket)
    # Do not validate rules here, rely on acl.set_acl's validation.
    bucket_acl = acl.BucketAcl(
        rules=[
            acl.Rule(
                role=rule.role,
                group=rule.group,
            )
            for rule in request.rules
        ],
    )
    bucket_acl = acl.set_acl(request.bucket, bucket_acl)
    return bucket_acl_to_response_message(bucket_acl)
