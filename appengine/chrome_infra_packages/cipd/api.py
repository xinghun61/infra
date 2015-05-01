# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Cloud Endpoints API for Package Repository service."""

import functools

import endpoints

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from components import auth
from components import utils

from . import acl
from . import client
from . import impl


# This is used by endpoints indirectly.
package = 'cipd'


################################################################################
## Messages used by other messages.


class Status(messages.Enum):
  """Response status code, shared by all responses."""
  # Operation finished successfully (generic "success" response).
  SUCCESS = 1
  # The package was successfully registered.
  REGISTERED = 2
  # The package was already registered (not a error).
  ALREADY_REGISTERED = 3
  # Some uncategorized non-transient error happened.
  ERROR = 4
  # No such package.
  PACKAGE_NOT_FOUND = 5
  # Package itself is known, but requested instance_id isn't registered.
  INSTANCE_NOT_FOUND = 6
  # Need to upload package data before registering the package.
  UPLOAD_FIRST = 7
  # Client binary is not available, the call should be retried later.
  NOT_EXTRACTED_YET = 8


class Package(messages.Message):
  """Information about some registered package."""
  package_name = messages.StringField(1, required=True)
  registered_by = messages.StringField(2, required=True)
  registered_ts = messages.IntegerField(3, required=True)


def package_to_proto(ent):
  """Package entity -> Package proto message."""
  return Package(
      package_name=ent.package_name,
      registered_by=ent.registered_by.to_bytes(),
      registered_ts=utils.datetime_to_timestamp(ent.registered_ts))


class PackageInstance(messages.Message):
  """Information about some registered package instance."""
  package_name = messages.StringField(1, required=True)
  instance_id = messages.StringField(2, required=True)
  registered_by = messages.StringField(3, required=True)
  registered_ts = messages.IntegerField(4, required=True)


def instance_to_proto(ent):
  """PackageInstance entity -> PackageInstance proto message."""
  return PackageInstance(
      package_name=ent.package_name,
      instance_id=ent.instance_id,
      registered_by=ent.registered_by.to_bytes(),
      registered_ts=utils.datetime_to_timestamp(ent.registered_ts))


class PackageACL(messages.Message):
  """Access control list for some package path and all parent paths."""

  class ElementaryACL(messages.Message):
    """Single per role, per package path ACL."""
    package_path = messages.StringField(1, required=True)
    role = messages.StringField(2, required=True)
    principals = messages.StringField(3, repeated=True)
    modified_by = messages.StringField(4, required=True)
    modified_ts = messages.IntegerField(5, required=True)

  # List of ACLs split by package path and role. No ordering.
  acls = messages.MessageField(ElementaryACL, 1, repeated=True)


def package_acls_to_proto(per_role_acls):
  """Dict {role -> list of PackageACL entities} -> PackageACL message."""
  acls = []
  for role, package_acl_entities in per_role_acls.iteritems():
    for e in package_acl_entities:
      principals = []
      principals.extend(u.to_bytes() for u in e.users)
      principals.extend('group:%s' % g for g in e.groups)
      acls.append(PackageACL.ElementaryACL(
          package_path=e.package_path,
          role=role,
          principals=principals,
          modified_by=e.modified_by.to_bytes(),
          modified_ts=utils.datetime_to_timestamp(e.modified_ts),
      ))
  return PackageACL(acls=acls)


class RoleChange(messages.Message):
  """Describes a single modification to ACL."""
  class Action(messages.Enum):
    GRANT = 1
    REVOKE = 2
  # Action to perform.
  action = messages.EnumField(Action, 1, required=True)
  # Role to modify ('OWNER', 'WRITER', 'READER', ...).
  role = messages.StringField(2, required=True)
  # Principal ('user:...' or 'group:...') to grant or revoke a role for.
  principal = messages.StringField(3, required=True)


def role_change_from_proto(proto, package_path):
  """RoleChange proto message -> acl.RoleChange object.

  Raises ValueError on format errors.
  """
  if not acl.is_valid_role(proto.role):
    raise ValueError('Invalid role %s' % proto.role)

  user = None
  group = None
  if proto.principal.startswith('group:'):
    group = proto.principal[len('group:'):]
    if not auth.is_valid_group_name(group):
      raise ValueError('Invalid group name: "%s"' % group)
  else:
    # Raises ValueError if proto.user has invalid format, e.g. not 'user:...'.
    user = auth.Identity.from_bytes(proto.principal)

  return acl.RoleChange(
      package_path=package_path,
      revoke=(proto.action != RoleChange.Action.GRANT),
      role=proto.role,
      user=user,
      group=group)


################################################################################


class FetchPackageResponse(messages.Message):
  """Results of fetchPackage call."""

  # TODO(vadimsh): Add more info (like a list of labels or instances).

  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, information about the package.
  package = messages.MessageField(Package, 3, required=False)


################################################################################


class RegisterPackageResponse(messages.Message):
  """Results of registerPackage call."""

  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For REGISTERED or ALREADY_REGISTERED, information about the package.
  package = messages.MessageField(Package, 3, required=False)


################################################################################


class FetchInstanceResponse(messages.Message):
  """Results of fetchInstance call."""
  class Processor(messages.Message):
    class Status(messages.Enum):
      PENDING = 1
      SUCCESS = 2
      FAILURE = 3
    # Name of the processor, defines what it does.
    name = messages.StringField(1, required=True)
    # Status of the processing.
    status = messages.EnumField(Status, 2, required=True)

  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, information about the package instance.
  instance = messages.MessageField(PackageInstance, 3, required=False)
  # For SUCCESS, a signed url to fetch the package instance file from.
  fetch_url = messages.StringField(4, required=False)
  # For SUCCESS, list of processors applies to the instance.
  processors = messages.MessageField(Processor, 5, repeated=True)


################################################################################


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
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For REGISTERED or ALREADY_REGISTERED, info about the package instance.
  instance = messages.MessageField(PackageInstance, 3, required=False)

  # For UPLOAD_FIRST status, a unique identifier of the upload operation.
  upload_session_id = messages.StringField(4, required=False)
  # For UPLOAD_FIRST status, URL to PUT file to via resumable upload protocol.
  upload_url = messages.StringField(5, required=False)


################################################################################


class FetchACLResponse(messages.Message):
  """Results of fetchACL call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS status, list of ACLs split by package path and role.
  acls = messages.MessageField(PackageACL, 3, required=False)


################################################################################


class ModifyACLRequest(messages.Message):
  """Body of modifyACL call."""
  changes = messages.MessageField(RoleChange, 1, repeated=True)


class ModifyACLResponse(messages.Message):
  """Results of modifyACL call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)


################################################################################


class FetchClientBinaryResponse(messages.Message):
  """Results of fetchClientBinary call."""
  class ClientBinary(messages.Message):
    # SHA1 hex digest of the extracted binary, for verification on the client.
    sha1 = messages.StringField(1, required=True)
    # Size of the binary file, just for information.
    size = messages.IntegerField(2, required=True)
    # A signed url to fetch the binary file from.
    fetch_url = messages.StringField(3, required=True)

  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS or NOT_EXTRACTED_YET, information about the package instance.
  instance = messages.MessageField(PackageInstance, 3, required=False)
  # For SUCCESS, information about the client binary.
  client_binary = messages.MessageField(ClientBinary, 4, required=False)


################################################################################


class Error(Exception):
  status = Status.ERROR


class PackageNotFoundError(Error):
  status = Status.PACKAGE_NOT_FOUND


class InstanceNotFoundError(Error):
  status = Status.INSTANCE_NOT_FOUND


class ValidationError(Error):
  # TODO(vadimsh): Use VALIDATION_ERROR. It changes JSON protocol.
  status = Status.ERROR


def validate_package_name(package_name):
  if not impl.is_valid_package_path(package_name):
    raise ValidationError('Invalid package name')
  return package_name


def validate_package_path(package_path):
  if not impl.is_valid_package_path(package_path):
    raise ValidationError('Invalid package path')
  return package_path


def validate_instance_id(instance_id):
  if not impl.is_valid_instance_id(instance_id):
    raise ValidationError('Invalid package instance ID')
  return instance_id


def endpoints_method(request_message, response_message, **kwargs):
  """Wrapper around Endpoint methods to simplify error handling.

  Catches Error exceptions and converts them to error responses. Assumes
  response_message has fields 'status' and 'error_message'.
  """
  assert hasattr(response_message, 'status')
  assert hasattr(response_message, 'error_message')
  def decorator(f):
    @auth.endpoints_method(request_message, response_message, **kwargs)
    @functools.wraps(f)
    def wrapper(*args):
      try:
        response = f(*args)
        if response.status is None:
          response.status = Status.SUCCESS
        return response
      except Error as e:
        return response_message(
            status=e.status,
            error_message=e.message if e.message else None)
    return wrapper
  return decorator


def container(body_cls, params):
  """Sugar for endpoints.ResourceContainer(...)."""
  kwargs = {}
  for idx, param in enumerate(params):
    kwargs[param] = messages.StringField(idx+1, required=True)
  return endpoints.ResourceContainer(body_cls, **kwargs)


################################################################################


@auth.endpoints_api(
    name='repo',
    version='v1',
    title='Package Repository API')
class PackageRepositoryApi(remote.Service):
  """Package Repository API."""

  # Cached value of 'service' property.
  _service = None

  @property
  def service(self):
    """Returns configured impl.RepoService."""
    if self._service is None:
      self._service = impl.get_repo_service()
      if self._service is None or not self._service.is_fetch_configured():
        raise endpoints.InternalServerErrorException(
            'Service is not configured')
    return self._service


  ### Package methods.


  @endpoints_method(
      container(message_types.VoidMessage, ['package_name']),
      FetchPackageResponse,
      http_method='GET',
      path='package',
      name='fetchPackage')
  def fetch_package(self, request):
    """Returns information about a package."""
    package_name = validate_package_name(request.package_name)

    caller = auth.get_current_identity()
    if not acl.can_fetch_package(package_name, caller):
      raise auth.AuthorizationError()

    pkg = self.service.get_package(package_name)
    if pkg is None:
      raise PackageNotFoundError()
    return FetchPackageResponse(package=package_to_proto(pkg))

  @endpoints_method(
      container(message_types.VoidMessage, ['package_name']),
      RegisterPackageResponse,
      path='package',
      http_method='POST',
      name='registerPackage')
  def register_package(self, request):
    """Registers a new package in the repository."""
    package_name = validate_package_name(request.package_name)

    caller = auth.get_current_identity()
    if not acl.can_register_package(package_name, caller):
      raise auth.AuthorizationError()

    pkg, registered = self.service.register_package(package_name, caller)
    return RegisterPackageResponse(
        status=Status.REGISTERED if registered else Status.ALREADY_REGISTERED,
        package=package_to_proto(pkg))


  ### PackageInstance methods.


  @endpoints_method(
      container(message_types.VoidMessage, ['package_name', 'instance_id']),
      FetchInstanceResponse,
      http_method='GET',
      path='instance',
      name='fetchInstance')
  def fetch_instance(self, request):
    """Returns signed URL that can be used to fetch a package instance."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()

    instance = self.service.get_instance(package_name, instance_id)
    if instance is None:
      pkg = self.service.get_package(package_name)
      if pkg is None:
        raise PackageNotFoundError()
      raise InstanceNotFoundError()

    def procs_to_msg(procs, status):
      return [
        FetchInstanceResponse.Processor(name=name, status=status)
        for name in procs
      ]
    processors = []
    processors += procs_to_msg(
        instance.processors_pending,
        FetchInstanceResponse.Processor.Status.PENDING)
    processors += procs_to_msg(
        instance.processors_success,
        FetchInstanceResponse.Processor.Status.SUCCESS)
    processors += procs_to_msg(
        instance.processors_failure,
        FetchInstanceResponse.Processor.Status.FAILURE)

    return FetchInstanceResponse(
        instance=instance_to_proto(instance),
        fetch_url=self.service.generate_fetch_url(instance),
        processors=processors)

  @endpoints_method(
      container(message_types.VoidMessage, ['package_name', 'instance_id']),
      RegisterInstanceResponse,
      path='instance',
      http_method='POST',
      name='registerInstance')
  def register_instance(self, request):
    """Registers a new package instance in the repository."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)

    caller = auth.get_current_identity()
    if not acl.can_register_instance(package_name, caller):
      raise auth.AuthorizationError()

    instance = self.service.get_instance(package_name, instance_id)
    if instance is not None:
      return RegisterInstanceResponse(
          status=Status.ALREADY_REGISTERED,
          instance=instance_to_proto(instance))

    # If the package is missing, check that user is actually allowed to make it.
    pkg = self.service.get_package(package_name)
    if pkg is None and not acl.can_register_package(package_name, caller):
      raise auth.AuthorizationError()

    # Need to upload to CAS first? Open an upload session. Caller must use
    # CASServiceApi to finish the upload and then call registerInstance again.
    if not self.service.is_instance_file_uploaded(package_name, instance_id):
      upload_url, upload_session_id = self.service.create_upload_session(
          package_name, instance_id, caller)
      return RegisterInstanceResponse(
          status=Status.UPLOAD_FIRST,
          upload_session_id=upload_session_id,
          upload_url=upload_url)

    # Package data is in the store. Make an entity.
    instance, registered = self.service.register_instance(
        package_name=package_name,
        instance_id=instance_id,
        caller=caller,
        now=utils.utcnow())
    return RegisterInstanceResponse(
        status=Status.REGISTERED if registered else Status.ALREADY_REGISTERED,
        instance=instance_to_proto(instance))


  ### ACL methods.


  @endpoints_method(
      container(message_types.VoidMessage, ['package_path']),
      FetchACLResponse,
      http_method='GET',
      path='acl',
      name='fetchACL')
  def fetch_acl(self, request):
    """Returns access control list for a given package path."""
    package_path = validate_package_path(request.package_path)

    caller = auth.get_current_identity()
    if not acl.can_fetch_acl(package_path, caller):
      raise auth.AuthorizationError()

    return FetchACLResponse(
        acls=package_acls_to_proto({
          role: acl.get_package_acls(package_path, role)
          for role in acl.ROLES
        }))

  @endpoints_method(
      container(ModifyACLRequest, ['package_path']),
      ModifyACLResponse,
      http_method='POST',
      path='acl',
      name='modifyACL')
  def modify_acl(self, request):
    """Changes access control list for a given package path."""
    package_path = validate_package_path(request.package_path)

    try:
      changes = [
        role_change_from_proto(msg, package_path)
        for msg in request.changes
      ]
    except ValueError as exc:
      raise ValidationError('Invalid role change request: %s' % exc)

    caller = auth.get_current_identity()
    if not acl.can_modify_acl(package_path, caller):
      raise auth.AuthorizationError()
    # Modifying ACLs for a package subpath implicitly creates an empty package.
    # That way acl.PackageACL entities always correspond to some existing
    # packages (impl.Package entities). It also simplifies registering new
    # packages: setting custom ACL on a package path is enough to register
    # a package. If custom ACL is not required, registerPackage method can be
    # used instead.
    now = utils.utcnow()
    assert acl.can_register_package(package_path, caller)
    self.service.register_package(package_path, caller, now)

    # Apply changes. Do not catch ValueError. Validation above should be
    # sufficient. If it is not, HTTP 500 and an uncaught exception in logs is
    # exactly what is needed.
    acl.modify_roles(changes, caller, now)
    return ModifyACLResponse()


  ### ClientBinary methods.


  @endpoints_method(
      container(message_types.VoidMessage, ['package_name', 'instance_id']),
      FetchClientBinaryResponse,
      http_method='GET',
      path='client',
      name='fetchClientBinary')
  def fetch_client_binary(self, request):
    """Returns signed URL that can be used to fetch CIPD client binary."""
    package_name = validate_package_name(request.package_name)
    if not client.is_cipd_client_package(package_name):
      raise ValidationError('Not a CIPD client package')
    instance_id = validate_instance_id(request.instance_id)

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()

    instance = self.service.get_instance(package_name, instance_id)
    if instance is None:
      pkg = self.service.get_package(package_name)
      if pkg is None:
        raise PackageNotFoundError()
      raise InstanceNotFoundError()

    # Grab the location of the extracted binary.
    client_info, error_message = self.service.get_client_binary_info(instance)
    if error_message:
      raise Error(error_message)
    if client_info is None:
      return FetchClientBinaryResponse(
        status=Status.NOT_EXTRACTED_YET,
        instance=instance_to_proto(instance))

    return FetchClientBinaryResponse(
        instance=instance_to_proto(instance),
        client_binary=FetchClientBinaryResponse.ClientBinary(
            sha1=client_info.sha1,
            size=client_info.size,
            fetch_url=client_info.fetch_url))
