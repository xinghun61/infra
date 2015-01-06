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


class RegisterPackageRequest(messages.Message):
  """Request to add a new package instance if it is not yet present.

  Callers are expected to execute following protocol:
    1. Attempt to register a package instance by calling registerPackage(msg).
    2. On UPLOAD_FIRST response, upload package data and finalize the upload by
       using upload_session_id and upload_url and calling cas.finishUpload.
    3. Once upload is finalized, call registerPackage(msg) again.
  """
  package_name = messages.StringField(1, required=True)
  instance_id = messages.StringField(2, required=True)


class RegisterPackageResponse(messages.Message):
  """Results of registerPackage call.

  upload_session_id and upload_url (if present) can be used with CAS service
  (finishUpload call in particular).
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

  # For REGISTERED and ALREADY_REGISTERED, who registered the package.
  registered_by = messages.StringField(2, required=False)
  # For REGISTERED and ALREADY_REGISTERED, when the package was registered.
  registered_ts = messages.IntegerField(3, required=False)

  # For UPLOAD_FIRST status, a unique identifier of the upload operation.
  upload_session_id = messages.StringField(4, required=False)
  # For UPLOAD_FIRST status, URL to PUT file to via resumable upload protocol.
  upload_url = messages.StringField(5, required=False)

  # For ERROR status, a error message.
  error_message = messages.StringField(6, required=False)


@auth.endpoints_api(
    name='repo',
    version='v1',
    title='Package Repository API')
class PackageRepositoryApi(remote.Service):
  """Package Repository API."""

  @auth.endpoints_method(
      RegisterPackageRequest,
      RegisterPackageResponse,
      http_method='POST',
      name='registerPackage')
  @auth.require(lambda: not auth.get_current_identity().is_anonymous)
  def register_package(self, request):
    """Registers a new package instance in the repository."""
    # Forms ERROR response.
    def error(msg):
      return RegisterPackageResponse(
          status=RegisterPackageResponse.Status.ERROR,
          error_message=msg)

    # Forms REGISTERED or ALREADY_REGISTERED response.
    def success(pkg, status):
      return RegisterPackageResponse(
          status=status,
          registered_by=pkg.registered_by.to_bytes(),
          registered_ts=utils.datetime_to_timestamp(pkg.registered_ts))

    package_name = request.package_name
    if not impl.is_valid_package_name(package_name):
      return error('Invalid package name')

    instance_id = request.instance_id
    if not impl.is_valid_instance_id(request.instance_id):
      return error('Invalid package instance ID')

    caller = auth.get_current_identity()
    if not acl.can_register_package(package_name, caller):
      raise auth.AuthorizationError()

    service = impl.get_repo_service()
    if service is None:
      raise endpoints.InternalServerErrorException('Service is not configured')

    # Already registered?
    pkg = service.get_instance(package_name, instance_id)
    if pkg is not None:
      return success(pkg, RegisterPackageResponse.Status.ALREADY_REGISTERED)

    # Need to upload to CAS first? Open an upload session. Caller must use
    # CASServiceApi to finish the upload and then call registerPackage again.
    if not service.is_instance_file_uploaded(package_name, instance_id):
      upload_url, upload_session_id = service.create_upload_session(
          package_name, instance_id, caller)
      return RegisterPackageResponse(
          status=RegisterPackageResponse.Status.UPLOAD_FIRST,
          upload_session_id=upload_session_id,
          upload_url=upload_url)

    # Package data is in the store. Make an entity.
    pkg, registered = service.register_instance(
        package_name=package_name,
        instance_id=instance_id,
        caller=caller,
        now=utils.utcnow())
    if registered:
      status = RegisterPackageResponse.Status.REGISTERED
    else:  # pragma: no cover
      status = RegisterPackageResponse.Status.ALREADY_REGISTERED
    return success(pkg, status)
