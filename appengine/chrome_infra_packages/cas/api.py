# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Cloud Endpoints API for Content Addressable Storage."""

import endpoints

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from components import auth

from . import impl


# This is used by endpoints indirectly.
package = 'cipd'


class HashAlgo(messages.Enum):
  SHA1 = 1


class FetchResponse(messages.Message):
  class Status(messages.Enum):
    # File is available for fetch.
    SUCCESS = 1
    # No such file uploaded.
    NOT_FOUND = 2
    # Some non-transient error happened.
    ERROR = 3

  # Status of the operation.
  status = messages.EnumField(Status, 1, required=True)
  # For SUCCESS status, a signed URL to fetch the file from.
  fetch_url = messages.StringField(2, required=False)
  # For ERROR status, an error message.
  error_message = messages.StringField(3, required=False)


class BeginUploadResponse(messages.Message):
  class Status(messages.Enum):
    # New upload session has started.
    SUCCESS = 1
    # Such file is already uploaded to the store.
    ALREADY_UPLOADED = 2
    # Some non-transient error happened.
    ERROR = 3

  # Status of this operation, defines what other fields to expect.
  status = messages.EnumField(Status, 1, required=True)

  # For SUCCESS status, a unique identifier of the upload operation.
  upload_session_id = messages.StringField(2, required=False)
  # For SUCCESS status, URL to PUT file body to via resumable upload protocol.
  upload_url = messages.StringField(3, required=False)

  # For ERROR status, an error message.
  error_message = messages.StringField(4, required=False)


class FinishUploadResponse(messages.Message):
  class Status(messages.Enum):
    # Upload session never existed or already expired.
    MISSING = impl.UploadSession.STATUS_MISSING
    # Client is still uploading the file.
    UPLOADING = impl.UploadSession.STATUS_UPLOADING
    # Server is verifying the hash of the uploaded file.
    VERIFYING = impl.UploadSession.STATUS_VERIFYING
    # The file is in the store and visible by all clients. Final state.
    PUBLISHED = impl.UploadSession.STATUS_PUBLISHED
    # Some non-transient error happened.
    ERROR = impl.UploadSession.STATUS_ERROR

  # Status of the upload operation.
  status = messages.EnumField(Status, 1, required=True)
  # For ERROR status, an error message.
  error_message = messages.StringField(2, required=False)


# int status -> Enum status.
_UPLOAD_STATUS_MAPPING = {
  getattr(impl.UploadSession, k): getattr(
      FinishUploadResponse.Status, k[len('STATUS_'):])
  for k in dir(impl.UploadSession) if k.startswith('STATUS_')
}

# HashAlgo enum field -> hash algo name. Also asserts that all algorithms
# specified in impl.SUPPORTED_HASH_ALGOS are in the HashAlgo enum.
_HASH_ALGO_MAPPING = {
  getattr(HashAlgo, k): k for k in impl.SUPPORTED_HASH_ALGOS
}


@auth.endpoints_api(
    name='cas',
    version='v1',
    title='Content Addressable Storage API')
class CASServiceApi(remote.Service):
  """Content addressable storage API."""

  # Endpoints require use of ResourceContainer if parameters are passed via URL.
  ITEM_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      # Hash algorithm used to identify file contents, e.g. 'SHA1'.
      hash_algo = messages.EnumField(HashAlgo, 1, required=True),
      # Hex hash digest of a file client wants to upload.
      file_hash = messages.StringField(2, required=True))

  @auth.endpoints_method(
      ITEM_RESOURCE_CONTAINER,
      FetchResponse,
      path='fetch/{hash_algo}/{file_hash}',
      http_method='GET',
      name='fetch')
  @auth.require(auth.is_admin)
  def fetch(self, request):
    """Returns a signed URL that can be used to fetch an object."""
    def error(msg):
      return FetchResponse(status=FetchResponse.Status.ERROR, error_message=msg)

    hash_algo = _HASH_ALGO_MAPPING[request.hash_algo]
    if not impl.is_valid_hash_digest(hash_algo, request.file_hash):
      return error('Invalid hash digest format')

    service = impl.get_cas_service()
    if service is None or not service.is_fetch_configured():
      raise endpoints.InternalServerErrorException('Service is not configured')

    url = service.generate_fetch_url(hash_algo, request.file_hash)
    return FetchResponse(status=FetchResponse.Status.SUCCESS, fetch_url=url)

  @auth.endpoints_method(
      ITEM_RESOURCE_CONTAINER,
      BeginUploadResponse,
      path='upload/{hash_algo}/{file_hash}',
      http_method='POST',
      name='beginUpload')
  @auth.require(auth.is_admin)
  def begin_upload(self, request):
    """Initiates an upload operation if file is missing.

    Once initiated the client is then responsible for uploading the file to
    temporary location (returned as 'upload_url') and finalizing the upload
    with call to 'finishUpload'.

    If file is already in the store, returns ALREADY_UPLOADED status.

    This method is not intended to be used directly by all clients (only by
    admins in case some files has to be injected into CAS store directly). Use
    PackageRepositoryApi.register_package instead to initiate an upload of some
    package and get upload_url and upload_session_id.
    """
    def error(msg):
      return BeginUploadResponse(
          status=BeginUploadResponse.Status.ERROR,
          error_message=msg)

    hash_algo = _HASH_ALGO_MAPPING[request.hash_algo]
    if not impl.is_valid_hash_digest(hash_algo, request.file_hash):
      return error('Invalid hash digest format')

    service = impl.get_cas_service()
    if service is None:
      raise endpoints.InternalServerErrorException('Service is not configured')

    if service.is_object_present(hash_algo, request.file_hash):
      return BeginUploadResponse(
          status=BeginUploadResponse.Status.ALREADY_UPLOADED)

    upload_session, upload_session_id = service.create_upload_session(
        hash_algo,
        request.file_hash,
        auth.get_current_identity())
    return BeginUploadResponse(
        status=BeginUploadResponse.Status.SUCCESS,
        upload_session_id=upload_session_id,
        upload_url=upload_session.upload_url)

  # Endpoints require use of ResourceContainer if parameters are passed via URL.
  FINISH_UPLOAD_RESOURCE_CONTAINER = endpoints.ResourceContainer(
      message_types.VoidMessage,
      # Upload operation ID as returned by beginUpload.
      upload_session_id = messages.StringField(1, required=True))

  @auth.endpoints_method(
      FINISH_UPLOAD_RESOURCE_CONTAINER,
      FinishUploadResponse,
      path='finalize/{upload_session_id}',
      http_method='POST',
      name='finishUpload')
  @auth.require(lambda: not auth.get_current_identity().is_anonymous)
  def finish_upload(self, request):
    """Finishes pending upload or queries its status.

    Client should finalize Google Storage upload session first. Once GS upload
    is finalized and 'finishUpload' is called, the server starts hash
    verification. Uploading client will get 'VERIFYING' status response. It
    can continue polling on this method until server returns 'PUBLISHED' status.

    upload_session_id implicitly authorizes the request.
    """
    service = impl.get_cas_service()
    if service is None:
      raise endpoints.InternalServerErrorException('Service is not configured')

    # Verify the signature if upload_session_id and grab the session. Broken
    # or expired signatures are treated in same way as missing upload sessions.
    # No need to provide more hits to the malicious caller.
    upload_session = service.fetch_upload_session(
        request.upload_session_id, auth.get_current_identity())
    if upload_session is None:
      return FinishUploadResponse(status=FinishUploadResponse.Status.MISSING)

    # Start object verification task if necessary, returns updated copy of
    # |upload_session| entity.
    upload_session = service.maybe_finish_upload(upload_session)

    response = FinishUploadResponse(
        status=_UPLOAD_STATUS_MAPPING[upload_session.status])
    if upload_session.status == impl.UploadSession.STATUS_ERROR:
      response.error_message = upload_session.error_message or 'Unknown error'
    return response
