# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Cloud Endpoints API for Package Repository service."""

import endpoints

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from components import auth
from components import utils

from . import acl
from . import impl


# This is used by endpoints indirectly.
package = 'cipd'


class PackageInstance(messages.Message):
  """Information about some registered package instance."""
  # Name of the package.
  package_name = messages.StringField(1, required=True)
  # ID of the instance (SHA1 of package file content).
  instance_id = messages.StringField(2, required=True)
  # Who registered the instance.
  registered_by = messages.StringField(3, required=True)
  # When the instance was registered.
  registered_ts = messages.IntegerField(4, required=True)


def instance_to_proto(ent):
  """PackageInstance entity -> PackageInstance proto message."""
  return PackageInstance(
      package_name=ent.package_name,
      instance_id=ent.instance_id,
      registered_by=ent.registered_by.to_bytes(),
      registered_ts=utils.datetime_to_timestamp(ent.registered_ts))


class FetchInstanceResponse(messages.Message):
  """Results of fetchInstance call."""

  class Status(messages.Enum):
    # Package instance exists, fetch_url is returned.
    SUCCESS = 1
    # No such package or access is denied.
    PACKAGE_NOT_FOUND = 2
    # Package itself is known, but requested instance_id isn't registered.
    INSTANCE_NOT_FOUND = 3
    # Some non-transient error happened.
    ERROR = 4

  # Status of this operation, defines what other fields to expect.
  status = messages.EnumField(Status, 1, required=True)

  # For SUCCESS, an information about the package instance.
  instance = messages.MessageField(PackageInstance, 2, required=False)
  # For SUCCESS, a signed url to fetch the package instance file from.
  fetch_url = messages.StringField(3, required=False)

  # For ERROR status, an error message.
  error_message = messages.StringField(4, required=False)


class RegisterInstanceResponse(messages.Message):
  """Results of registerInstance call.

  upload_session_id and upload_url (if present) can be used with CAS service
  (finishUpload call in particular).

  Callers are expected to execute following protocol:
    1. Attempt to register a package instance by calling registerInstance(...).
    2. On UPLOAD_FIRST response, upload package data and finalize the upload by
       using upload_session_id and upload_url and calling cas.finishUpload.
    3. Once upload is finalized, call registerInstance(...) again.
  """

  class Status(messages.Enum):
    # Package instance successfully registered.
    REGISTERED = 1
    # Such package instance already exists. It is not an error.
    ALREADY_REGISTERED = 2
    # Package data has to be upload to CAS first.
    UPLOAD_FIRST = 3
    # Some unexpected fatal error happened.
    ERROR = 4

  # Status of this operation, defines what other fields to expect.
  status = messages.EnumField(Status, 1, required=True)

  # For REGISTERED or ALREADY_REGISTERED, info about the package instance.
  instance = messages.MessageField(PackageInstance, 2, required=False)

  # For UPLOAD_FIRST status, a unique identifier of the upload operation.
  upload_session_id = messages.StringField(3, required=False)
  # For UPLOAD_FIRST status, URL to PUT file to via resumable upload protocol.
  upload_url = messages.StringField(4, required=False)

  # For ERROR status, an error message.
  error_message = messages.StringField(5, required=False)


@auth.endpoints_api(
    name='repo',
    version='v1',
    title='Package Repository API')
class PackageRepositoryApi(remote.Service):
  """Package Repository API."""

  # Identified some instance of some package.
  INSTANCE_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      package_name = messages.StringField(1, required=True),
      instance_id = messages.StringField(2, required=True))

  @auth.endpoints_method(
      INSTANCE_RESOURCE_CONTAINER,
      FetchInstanceResponse,
      http_method='GET',
      path='instance',
      name='fetchInstance')
  def fetch_instance(self, request):
    """Returns signed URL that can be used to fetch a package instance."""
    def error(msg):
      return FetchInstanceResponse(
          status=FetchInstanceResponse.Status.ERROR,
          error_message=msg)

    package_name = request.package_name
    if not impl.is_valid_package_name(package_name):
      return error('Invalid package name')

    instance_id = request.instance_id
    if not instance_id or not impl.is_valid_instance_id(instance_id):
      return error('Invalid package instance ID')

    # An unauthorized user should not be able to prob package namespace and rely
    # on 403 status to discover what packages exist. Return "not found" instead.
    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      return FetchInstanceResponse(
          status=FetchInstanceResponse.Status.PACKAGE_NOT_FOUND)

    service = impl.get_repo_service()
    if service is None or not service.is_fetch_configured():
      raise endpoints.InternalServerErrorException('Service is not configured')

    # Check that package and instance exist.
    instance = service.get_instance(package_name, instance_id)
    if instance is None:
      pkg = service.get_package(package_name)
      if pkg is None:
        return FetchInstanceResponse(
            status=FetchInstanceResponse.Status.PACKAGE_NOT_FOUND)
      return FetchInstanceResponse(
          status=FetchInstanceResponse.Status.INSTANCE_NOT_FOUND)

    # Success.
    return FetchInstanceResponse(
        status=FetchInstanceResponse.Status.SUCCESS,
        instance=instance_to_proto(instance),
        fetch_url=service.generate_fetch_url(instance))

  @auth.endpoints_method(
      INSTANCE_RESOURCE_CONTAINER,
      RegisterInstanceResponse,
      path='instance',
      http_method='POST',
      name='registerInstance')
  def register_instance(self, request):
    """Registers a new package instance in the repository."""
    # Forms ERROR response.
    def error(msg):
      return RegisterInstanceResponse(
          status=RegisterInstanceResponse.Status.ERROR,
          error_message=msg)

    # Forms REGISTERED or ALREADY_REGISTERED response.
    def success(instance, status):
      return RegisterInstanceResponse(
          status=status,
          instance=instance_to_proto(instance))

    package_name = request.package_name
    if not impl.is_valid_package_name(package_name):
      return error('Invalid package name')

    instance_id = request.instance_id
    if not impl.is_valid_instance_id(instance_id):
      return error('Invalid package instance ID')

    caller = auth.get_current_identity()
    if not acl.can_register_instance(package_name, caller):
      raise auth.AuthorizationError()

    service = impl.get_repo_service()
    if service is None:
      raise endpoints.InternalServerErrorException('Service is not configured')

    # Already registered?
    instance = service.get_instance(package_name, instance_id)
    if instance is not None:
      return success(
          instance, RegisterInstanceResponse.Status.ALREADY_REGISTERED)

    # Need to upload to CAS first? Open an upload session. Caller must use
    # CASServiceApi to finish the upload and then call registerInstance again.
    if not service.is_instance_file_uploaded(package_name, instance_id):
      upload_url, upload_session_id = service.create_upload_session(
          package_name, instance_id, caller)
      return RegisterInstanceResponse(
          status=RegisterInstanceResponse.Status.UPLOAD_FIRST,
          upload_session_id=upload_session_id,
          upload_url=upload_url)

    # Package data is in the store. Make an entity.
    instance, registered = service.register_instance(
        package_name=package_name,
        instance_id=instance_id,
        caller=caller,
        now=utils.utcnow())
    if registered:
      status = RegisterInstanceResponse.Status.REGISTERED
    else:  # pragma: no cover
      status = RegisterInstanceResponse.Status.ALREADY_REGISTERED
    return success(instance, status)
