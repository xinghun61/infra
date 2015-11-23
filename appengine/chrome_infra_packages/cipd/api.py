# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Cloud Endpoints API for Package Repository service."""

import functools
import logging

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
  # The package instance was successfully registered.
  REGISTERED = 2
  # The package instance was already registered (not a error).
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
  # Some asynchronous package processing failed.
  PROCESSING_FAILED = 9
  # Asynchronous package processing is still running.
  PROCESSING_NOT_FINISHED_YET = 10
  # More than one instance matches criteria in resolveVersion.
  AMBIGUOUS_VERSION = 11


class Package(messages.Message):
  """Information about some registered package."""
  package_name = messages.StringField(1, required=True)
  registered_by = messages.StringField(2, required=True)
  registered_ts = messages.IntegerField(3, required=True)


def package_to_proto(entity):
  """Package entity -> Package proto message."""
  return Package(
      package_name=entity.package_name,
      registered_by=entity.registered_by.to_bytes(),
      registered_ts=utils.datetime_to_timestamp(entity.registered_ts))


class PackageInstance(messages.Message):
  """Information about some registered package instance."""
  package_name = messages.StringField(1, required=True)
  instance_id = messages.StringField(2, required=True)
  registered_by = messages.StringField(3, required=True)
  registered_ts = messages.IntegerField(4, required=True)


def instance_to_proto(entity):
  """PackageInstance entity -> PackageInstance proto message."""
  return PackageInstance(
      package_name=entity.package_name,
      instance_id=entity.instance_id,
      registered_by=entity.registered_by.to_bytes(),
      registered_ts=utils.datetime_to_timestamp(entity.registered_ts))


class InstanceTag(messages.Message):
  """Some single package instance tag."""
  tag = messages.StringField(1, required=True)
  registered_by = messages.StringField(2, required=True)
  registered_ts = messages.IntegerField(3, required=True)


def tag_to_proto(entity):
  """InstanceTag entity -> InstanceTag proto message."""
  return InstanceTag(
      tag=entity.tag,
      registered_by=entity.registered_by.to_bytes(),
      registered_ts=utils.datetime_to_timestamp(entity.registered_ts))


class PackageRef(messages.Message):
  """Information about some ref belonging to a package."""
  ref = messages.StringField(1, required=True)
  instance_id = messages.StringField(2, required=True)
  modified_by = messages.StringField(3, required=True)
  modified_ts = messages.IntegerField(4, required=True)


def package_ref_to_proto(entity):
  """PackageRef entity -> PackageRef proto message."""
  return PackageRef(
      ref=entity.ref,
      instance_id=entity.instance_id,
      modified_by=entity.modified_by.to_bytes(),
      modified_ts=utils.datetime_to_timestamp(entity.modified_ts))


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


class Processor(messages.Message):
  """Status of some package instance processor."""
  class Status(messages.Enum):
    PENDING = 1
    SUCCESS = 2
    FAILURE = 3
  # Name of the processor, defines what it does.
  name = messages.StringField(1, required=True)
  # Status of the processing.
  status = messages.EnumField(Status, 2, required=True)


def processors_protos(instance):
  """Given PackageInstance entity returns a list of Processor messages."""
  def procs_to_msg(procs, status):
    return [Processor(name=name, status=status) for name in procs ]
  processors = []
  processors += procs_to_msg(
      instance.processors_pending,
      Processor.Status.PENDING)
  processors += procs_to_msg(
      instance.processors_success,
      Processor.Status.SUCCESS)
  processors += procs_to_msg(
      instance.processors_failure,
      Processor.Status.FAILURE)
  return processors


################################################################################


class FetchPackageResponse(messages.Message):
  """Results of fetchPackage call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, information about the package.
  package = messages.MessageField(Package, 3, required=False)
  refs = messages.MessageField(PackageRef, 4, repeated=True)


################################################################################


class ListPackagesResponse(messages.Message):
  """Results of listPackage call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, names of the packages and names of directories.
  packages = messages.StringField(3, repeated=True)
  directories = messages.StringField(4, repeated=True)


################################################################################


class DeletePackageResponse(messages.Message):
  """Results of deletePackage call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)


################################################################################


class FetchInstanceResponse(messages.Message):
  """Results of fetchInstance call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, information about the package instance.
  instance = messages.MessageField(PackageInstance, 3, required=False)
  # For SUCCESS, a signed url to fetch the package instance file from.
  fetch_url = messages.StringField(4, required=False)
  # For SUCCESS, list of processors applied to the instance.
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


class SetRefRequest(messages.Message):
  """Body of setRef call."""
  # ID of the package instance to point the ref too.
  instance_id = messages.StringField(1, required=True)


class SetRefResponse(messages.Message):
  """Results of setRef call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS status, details about the ref.
  ref = messages.MessageField(PackageRef, 3, required=False)


class FetchRefsResponse(messages.Message):
  """Results of fetchRefs call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS status, details about fetches refs.
  refs = messages.MessageField(PackageRef, 3, repeated=True)


################################################################################


class FetchTagsResponse(messages.Message):
  """Results of fetchTags call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS status, details about found tags.
  tags = messages.MessageField(InstanceTag, 3, repeated=True)


class AttachTagsRequest(messages.Message):
  """Body of attachTags call."""
  tags = messages.StringField(1, repeated=True)


class AttachTagsResponse(messages.Message):
  """Results of attachTag call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS status, details about attached tags.
  tags = messages.MessageField(InstanceTag, 3, repeated=True)


class DetachTagsResponse(messages.Message):
  """Results of detachTags call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)


################################################################################


class SearchResponse(messages.Message):
  """Results of searchInstances call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, list of instances found.
  instances = messages.MessageField(PackageInstance, 3, repeated=True)


class ResolveVersionResponse(messages.Message):
  """Results of resolveVersion call."""
  status = messages.EnumField(Status, 1, required=True)
  error_message = messages.StringField(2, required=False)

  # For SUCCESS, concrete existing instance ID.
  instance_id = messages.StringField(3, required=False)


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


class ProcessingFailedError(Error):
  status = Status.PROCESSING_FAILED


class ProcessingNotFinishedYetError(Error):
  status = Status.PROCESSING_NOT_FINISHED_YET


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


def validate_package_ref(ref):
  if not impl.is_valid_package_ref(ref):
    raise ValidationError('Invalid package ref name')
  return ref


def validate_package_ref_list(refs):
  if not refs:  # pragma: no cover
    raise ValidationError('Ref list is empty')
  return [validate_package_ref(ref) for ref in refs]


def validate_instance_id(instance_id):
  if not impl.is_valid_instance_id(instance_id):
    raise ValidationError('Invalid package instance ID')
  return instance_id


def validate_instance_tag(tag):
  if not impl.is_valid_instance_tag(tag):
    raise ValidationError('Invalid tag "%s"' % tag)
  return tag


def validate_instance_tag_list(tags):
  if not tags:
    raise ValidationError('Tag list is empty')
  return [validate_instance_tag(tag) for tag in tags]


def validate_instance_version(version):
  if not impl.is_valid_instance_version(version):
    raise ValidationError('Not a valid instance ID or tag: "%s"' % version)
  return version


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
      except auth.Error as e:
        caller = auth.get_current_identity().to_bytes()
        logging.warning('%s (%s): %s', e.__class__.__name__, caller, e)
        raise
    return wrapper
  return decorator


################################################################################


@auth.endpoints_api(
    name='repo',
    version='v1',
    title='CIPD Package Repository API')
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

  def get_instance(self, package_name, instance_id):
    """Grabs PackageInstance or raises appropriate *NotFoundError."""
    instance = self.service.get_instance(package_name, instance_id)
    if instance is None:
      pkg = self.service.get_package(package_name)
      if pkg is None:
        raise PackageNotFoundError()
      raise InstanceNotFoundError()
    return instance

  def verify_instance_exists(self, package_name, instance_id):
    """Raises appropriate *NotFoundError if instance is missing."""
    self.get_instance(package_name, instance_id)

  def verify_instance_is_ready(self, package_name, instance_id):
    """Raises appropriate error if instance doesn't exist or not ready yet.

    Instance is ready when all processors successfully finished.
    """
    instance = self.get_instance(package_name, instance_id)
    if instance.processors_failure:
      raise ProcessingFailedError(
          'Failed processors: %s' % ', '.join(instance.processors_failure))
    if instance.processors_pending:
      raise ProcessingNotFinishedYetError(
          'Pending processors: %s' % ', '.join(instance.processors_pending))


  ### Package methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          with_refs=messages.BooleanField(2, required=False)),
      FetchPackageResponse,
      http_method='GET',
      path='package',
      name='fetchPackage')
  @auth.public  # ACL check is inside
  def fetch_package(self, request):
    """Returns information about a package."""
    package_name = validate_package_name(request.package_name)

    caller = auth.get_current_identity()
    if not acl.can_fetch_package(package_name, caller):
      raise auth.AuthorizationError()

    pkg = self.service.get_package(package_name)
    if pkg is None:
      raise PackageNotFoundError()

    refs = []
    if request.with_refs:
      refs = self.service.query_package_refs(package_name)

    return FetchPackageResponse(
        package=package_to_proto(pkg),
        refs=[package_ref_to_proto(r) for r in refs])

  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          path=messages.StringField(1, required=False),
          recursive=messages.BooleanField(2, required=False)),
      ListPackagesResponse,
      http_method='GET',
      path='package/search',
      name='listPackages')
  @auth.public  # ACL check is inside
  def list_packages(self, request):
    """Returns packages in the given directory and possibly subdirectories."""
    path = request.path or ''
    recursive = request.recursive or False

    pkgs, dirs = self.service.list_packages(path, recursive)
    caller = auth.get_current_identity()
    visible_pkgs = [p for p in pkgs if acl.can_fetch_package(p, caller)]
    visible_dirs = [d for d in dirs if acl.can_fetch_package(d, caller)]

    return ListPackagesResponse(packages=visible_pkgs, directories=visible_dirs)

  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True)),
      DeletePackageResponse,
      http_method='DELETE',
      path='package',
      name='deletePackage')
  @auth.public  # ACL check is inside
  def delete_package(self, request):
    """Deletes a package along with all its instances."""
    package_name = validate_package_name(request.package_name)

    caller = auth.get_current_identity()
    if not acl.can_delete_package(package_name, caller):
      raise auth.AuthorizationError()

    deleted = self.service.delete_package(package_name)
    if not deleted:
      raise PackageNotFoundError()
    return DeletePackageResponse()


  ### PackageInstance methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True)),
      FetchInstanceResponse,
      http_method='GET',
      path='instance',
      name='fetchInstance')
  @auth.public  # ACL check is inside
  def fetch_instance(self, request):
    """Returns signed URL that can be used to fetch a package instance."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()

    instance = self.get_instance(package_name, instance_id)
    return FetchInstanceResponse(
        instance=instance_to_proto(instance),
        fetch_url=self.service.generate_fetch_url(instance),
        processors=processors_protos(instance))

  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True)),
      RegisterInstanceResponse,
      path='instance',
      http_method='POST',
      name='registerInstance')
  @auth.public  # ACL check is inside
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


  ### Refs methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          SetRefRequest,
          package_name=messages.StringField(1, required=True),
          ref=messages.StringField(2, required=True)),
      SetRefResponse,
      path='ref',
      http_method='POST',
      name='setRef')
  @auth.public  # ACL check is inside
  def set_ref(self, request):
    """Creates a ref or moves an existing one."""
    package_name = validate_package_name(request.package_name)
    ref = validate_package_ref(request.ref)
    instance_id = validate_instance_id(request.instance_id)

    caller = auth.get_current_identity()
    if not acl.can_move_ref(package_name, ref, caller):
      raise auth.AuthorizationError('Not authorized to move "%s"' % ref)
    self.verify_instance_is_ready(package_name, instance_id)

    ref_entity = self.service.set_package_ref(
        package_name=package_name,
        ref=ref,
        instance_id=instance_id,
        caller=caller,
        now=utils.utcnow())
    return SetRefResponse(ref=package_ref_to_proto(ref_entity))

  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True),
          ref=messages.StringField(3, repeated=True)),
      FetchRefsResponse,
      path='ref',
      http_method='GET',
      name='fetchRefs')
  @auth.public  # ACL check is inside
  def fetch_refs(self, request):
    """Lists package instance refs (newest first)."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)
    refs = validate_package_ref_list(request.ref) if request.ref else None

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()
    self.verify_instance_exists(package_name, instance_id)

    if not refs:
      # Fetch all.
      output = self.service.query_instance_refs(package_name, instance_id)
    else:
      # Fetch selected refs, pick ones pointing to the instance.
      output = [
        r
        for r in self.service.get_package_refs(package_name, refs).itervalues()
        if r and r.instance_id == instance_id
      ]
      output.sort(key=lambda r: r.modified_ts, reverse=True)

    return FetchRefsResponse(refs=[package_ref_to_proto(ref) for ref in output])


  ### Tags methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True),
          tag=messages.StringField(3, repeated=True)),
      FetchTagsResponse,
      path='tags',
      http_method='GET',
      name='fetchTags')
  @auth.public  # ACL check is inside
  def fetch_tags(self, request):
    """Lists package instance tags (newest first)."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)
    tags = validate_instance_tag_list(request.tag) if request.tag else None

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()
    self.verify_instance_exists(package_name, instance_id)

    if not tags:
      # Fetch all.
      attached = self.service.query_tags(package_name, instance_id)
    else:
      # Fetch selected only. "Is tagged by?" check essentially.
      found = self.service.get_tags(package_name, instance_id, tags)
      attached = [found[tag] for tag in tags if found[tag]]
      attached.sort(key=lambda t: t.registered_ts, reverse=True)

    return FetchTagsResponse(tags=[tag_to_proto(tag) for tag in attached])

  @endpoints_method(
      endpoints.ResourceContainer(
          AttachTagsRequest,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True)),
      AttachTagsResponse,
      path='tags',
      http_method='POST',
      name='attachTags')
  @auth.public  # ACL check is inside
  def attach_tags(self, request):
    """Attaches a set of tags to a package instance."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)
    tags = validate_instance_tag_list(request.tags)

    caller = auth.get_current_identity()
    for tag in tags:
      if not acl.can_attach_tag(package_name, tag, caller):
        raise auth.AuthorizationError('Not authorized to attach "%s"' % tag)
    self.verify_instance_is_ready(package_name, instance_id)

    attached = self.service.attach_tags(
        package_name=package_name,
        instance_id=instance_id,
        tags=tags,
        caller=caller,
        now=utils.utcnow())
    return AttachTagsResponse(tags=[tag_to_proto(attached[t]) for t in tags])

  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True),
          tag=messages.StringField(3, repeated=True)),
      DetachTagsResponse,
      path='tags',
      http_method='DELETE',
      name='detachTags')
  @auth.public  # ACL check is inside
  def detach_tags(self, request):
    """Removes given tags from a package instance."""
    package_name = validate_package_name(request.package_name)
    instance_id = validate_instance_id(request.instance_id)
    tags = validate_instance_tag_list(request.tag)

    caller = auth.get_current_identity()
    for tag in tags:
      if not acl.can_detach_tag(package_name, tag, caller):
        raise auth.AuthorizationError('Not authorized to detach "%s"' % tag)
    self.verify_instance_exists(package_name, instance_id)

    self.service.detach_tags(
        package_name=package_name,
        instance_id=instance_id,
        tags=tags)
    return DetachTagsResponse()


  ### Search methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          tag=messages.StringField(1, required=True),
          package_name=messages.StringField(2, required=False)),
      SearchResponse,
      path='instance/search',
      http_method='GET',
      name='searchInstances')
  @auth.public  # ACL check is inside
  def search_instances(self, request):
    """Returns package instances with given tag (in no particular order)."""
    tag = validate_instance_tag(request.tag)
    if request.package_name:
      package_name = validate_package_name(request.package_name)
    else:
      package_name = None

    caller = auth.get_current_identity()
    callback = None
    if package_name:
      # If search is limited to one package, check its ACL only once.
      if not acl.can_fetch_instance(package_name, caller):
        raise auth.AuthorizationError()
    else:
      # Filter out packages not allowed by ACL.
      acl_cache = {}
      def check_readable(package_name, _instance_id):
        if package_name not in acl_cache:
          acl_cache[package_name] = acl.can_fetch_instance(package_name, caller)
        return acl_cache[package_name]
      callback = check_readable

    found = self.service.search_by_tag(tag, package_name, callback)
    return SearchResponse(instances=[instance_to_proto(i) for i in found])


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          version=messages.StringField(2, required=True)),
      ResolveVersionResponse,
      path='instance/resolve',
      http_method='GET',
      name='resolveVersion')
  @auth.public  # ACL check is inside
  def resolve_version(self, request):
    """Returns instance ID of an existing instance given a ref or a tag."""
    package_name = validate_package_name(request.package_name)
    version = validate_instance_version(request.version)

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()

    pkg = self.service.get_package(package_name)
    if pkg is None:
      raise PackageNotFoundError()

    ids = self.service.resolve_version(package_name, version, limit=2)
    if not ids:
      raise InstanceNotFoundError()
    if len(ids) > 1:
      return ResolveVersionResponse(
          status=Status.AMBIGUOUS_VERSION,
          error_message='More than one instance has tag "%s" set' % version)
    return ResolveVersionResponse(instance_id=ids[0])


  ### ACL methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_path=messages.StringField(1, required=True)),
      FetchACLResponse,
      http_method='GET',
      path='acl',
      name='fetchACL')
  @auth.public  # ACL check is inside
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
      endpoints.ResourceContainer(
          ModifyACLRequest,
          package_path=messages.StringField(1, required=True)),
      ModifyACLResponse,
      http_method='POST',
      path='acl',
      name='modifyACL')
  @auth.public  # ACL check is inside
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

    # Apply changes. Do not catch ValueError. Validation above should be
    # sufficient. If it is not, HTTP 500 and an uncaught exception in logs is
    # exactly what is needed.
    acl.modify_roles(changes, caller, utils.utcnow())
    return ModifyACLResponse()


  ### ClientBinary methods.


  @endpoints_method(
      endpoints.ResourceContainer(
          message_types.VoidMessage,
          package_name=messages.StringField(1, required=True),
          instance_id=messages.StringField(2, required=True)),
      FetchClientBinaryResponse,
      http_method='GET',
      path='client',
      name='fetchClientBinary')
  @auth.public  # ACL check is inside
  def fetch_client_binary(self, request):
    """Returns signed URL that can be used to fetch CIPD client binary."""
    package_name = validate_package_name(request.package_name)
    if not client.is_cipd_client_package(package_name):
      raise ValidationError('Not a CIPD client package')
    instance_id = validate_instance_id(request.instance_id)

    caller = auth.get_current_identity()
    if not acl.can_fetch_instance(package_name, caller):
      raise auth.AuthorizationError()

    # Grab the location of the extracted binary.
    instance = self.get_instance(package_name, instance_id)
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
