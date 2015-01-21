# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implementation of package repository service.

Definitions:
  * Package: a named set of files that can be deployed to a client. Package name
    is a path-like string, e.g. "infra/tools/cipd".
  * Package instance: concrete incarnation of a package, identified by SHA1 of
    the package file content. This hex SHA1 digest is referred to as
    "instance ID". Package files are deterministically built (i.e. same inputs
    produce exact same outputs) and thus instance IDs also depend only on the
    contents of the package.

Package instances are stored in the following way:
  * Package file itself is stored in CAS (implemented on top of Google Storage),
    using SHA1 content hash (i.e. instance ID) as identifier.
  * Package existence (as well as some metadata like when the package was
    registered) is stored in the Datastore in read-only entity (see
    PackageInstance class).

All PackageInstance that belong to the same package are stored in the same
entity group (with root key derived from package name, see Package entity).

Package entity (even though it is empty) is also instantiated in the datastore
to make possible querying for a list of known packages.

Once a package instance is uploaded, it may be asynchronously processed by
a number of "processors" that read and evaluate package contents producing some
summary. For example, a processor may ensure that the package has a valid format
and grab a list of package files to display in UI. Processing can finish with
any of two final states: success or failure. Transient errors are retried until
some definite result is known.
"""

import collections
import json
import logging
import re
import webapp2

from google.appengine import runtime
from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from components import auth
from components import decorators
from components import utils

import cas

from . import client
from . import processing
from . import reader


# Regular expression for a package name: <word>/<word/<word>. Package names must
# be lower case.
PACKAGE_NAME_RE = re.compile(r'^([a-z0-9_\-]+/)*[a-z0-9_\-]+$')

# Hash algorithm used to derive package instance ID from package data.
DIGEST_ALGO = 'SHA1'


# Information about extract CIPD client binary, see get_client_binary_info.
ClientBinaryInfo = collections.namedtuple(
    'ClientBinaryInfo', ['sha1', 'size', 'fetch_url'])


class RepoService(object):
  """Package repository service."""

  def __init__(self, cas_service, processors=None):
    """Initializes RepoService.

    Args:
      cas_service: instance of cas.CASService to use.
      processors: list of known processing.Processor instances.
    """
    self.cas_service = cas_service
    self.processors = processors or []

  def is_fetch_configured(self):
    """True if 'generate_fetch_url' has enough configuration to work."""
    return self.cas_service.is_fetch_configured()

  def get_instance(self, package_name, instance_id):
    """Returns PackageInstance entity if such instance is registered.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).

    Returns:
      PackageInstance or None.
    """
    return package_instance_key(package_name, instance_id).get()

  def get_package(self, package_name):
    """Returns Package entity if it exists.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.

    Returns:
      Package or None.
    """
    return package_key(package_name).get()

  def get_processing_result(self, package_name, instance_id, processor_name):
    """Returns results of some asynchronous processor or None if not ready.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      processor_name: name of the processor to retrieve results of.

    Returns:
      ProcessingResult entity or None.
    """
    return processing_result_key(
        package_name, instance_id, processor_name).get()

  @ndb.transactional
  def register_package(self, package_name, caller, now=None):
    """Ensures a given package is registered.

    Can be used by callers with OWNER role to create a package, without
    uploading any concrete instances. Such empty packages later are populated
    with instances by callers with WRITER role.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      caller: auth.Identity that issued the request.
      now: datetime when the request was made (or None for current time).

    Returns:
      Tuple (Package entity, True if registered or False if existed).
    """
    return self._register_package(package_name, caller, now)

  @ndb.transactional
  def register_instance(self, package_name, instance_id, caller, now=None):
    """Makes new PackageInstance entity if it is not yet there.

    Caller must verify that package data is already uploaded to CAS (by using
    is_instance_file_uploaded method).

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      caller: auth.Identity that issued the request.
      now: datetime when the request was made (or None for current time).

    Returns:
      Tuple (PackageInstance entity, True if registered or False if existed).
    """
    # Register the package and the instance if not already registered.
    key = package_instance_key(package_name, instance_id)
    inst = key.get()
    if inst is not None:
      return inst, False
    now = now or utils.utcnow()
    self._register_package(package_name, caller, now)
    inst = PackageInstance(
        key=key,
        registered_by=caller,
        registered_ts=now)

    # Trigger post processing, if any.
    processors = [p.name for p in self.processors if p.should_process(inst)]
    if processors:
      # ID in the URL is FYI only, to see what's running now via admin UI.
      success = utils.enqueue_task(
          url='/internal/taskqueue/cipd-process/%s' % instance_id,
          queue_name='cipd-process',
          payload=json.dumps({
            'package_name': package_name,
            'instance_id': instance_id,
            'processors': processors,
          }, sort_keys=True),
          transactional=True)
      if not success:  # pragma: no cover
        raise datastore_errors.TransactionFailedError()

    # Store the instance, remember what processors have been triggered.
    inst.processors_pending = processors
    inst.put()
    return inst, True

  def generate_fetch_url(self, instance):
    """Given PackageInstance returns signed URL to a package file.

    Args:
      instance: existing PackageInstance entity.

    Returns:
      Signed URL that can be used by a client to fetch package file.
    """
    assert self.is_fetch_configured()
    return self.cas_service.generate_fetch_url(
        DIGEST_ALGO, instance.instance_id)

  def get_client_binary_info(self, instance):
    """Returns URL to the client binary, its SHA1 hash and size.

    Used to get a direct URL to a client executable file. The file itself is
    uploaded by processing.ExtractCIPDClientProcessor step applied to packages
    for which client.is_cipd_client_package returns True ('infra/tools/cipd/*').

    Args:
      instance: PackageInstance entity corresponding to some registered and
          processed cipd client package.

    Returns:
      Tuple (ClientBinaryInfo, error message) where:
        a) ClientBinaryInfo is not None, error message is None on success.
        b) ClientBinaryInfo is None, error message is not None on error.
        c) Both items are None if client binary is still being extracted.
    """
    assert client.is_cipd_client_package(instance.package_name)
    assert self.is_fetch_configured()
    processing_result = self.get_processing_result(
        instance.package_name,
        instance.instance_id,
        client.CIPD_BINARY_EXTRACT_PROCESSOR)
    if processing_result is None:
      return None, None
    if not processing_result.success:
      return None, 'Failed to extract the binary: %s' % processing_result.error
    # See processing.ExtractCIPDClientProcessor for code that puts this data.
    # CIPD_BINARY_EXTRACT_PROCESSOR includes a version number that is bumped
    # whenever format of the data changes, so assume the data is correct.
    data = processing_result.result.get('client_binary')
    assert isinstance(data['size'], (int, long))
    assert data['hash_algo'] == 'SHA1'
    assert cas.is_valid_hash_digest('SHA1', data['hash_digest'])
    fetch_url = self.cas_service.generate_fetch_url('SHA1', data['hash_digest'])
    return ClientBinaryInfo(
        sha1=data['hash_digest'],
        size=data['size'],
        fetch_url=fetch_url), None

  def is_instance_file_uploaded(self, package_name, instance_id):
    """Returns True if package instance file is uploaded to CAS.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).

    Returns:
      True or False.
    """
    assert is_valid_package_path(package_name), package_name
    assert is_valid_instance_id(instance_id), instance_id
    return self.cas_service.is_object_present(DIGEST_ALGO, instance_id)

  def create_upload_session(self, package_name, instance_id, caller):
    """Opens a new session for data upload to CAS.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      caller: auth.Identity of whoever is opening an upload session.

    Returns:
      (upload URL to upload data to, upload session ID to pass to CAS API).
    """
    assert is_valid_package_path(package_name), package_name
    assert is_valid_instance_id(instance_id), instance_id
    upload_session, upload_session_id = self.cas_service.create_upload_session(
        DIGEST_ALGO, instance_id, caller)
    return upload_session.upload_url, upload_session_id

  def process_instance(self, package_name, instance_id, processors):
    """Performs the post processing step creating ProcessingResult entities.

    Called asynchronously from a task queue. Skips processors that have already
    ran. Can be retried by task queue service multiple times.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      processors: names of processors to run.
    """
    # The instance should be registered already.
    inst = self.get_instance(package_name, instance_id)
    assert inst, 'Instance %s:%s must exist' % (package_name, instance_id)

    # Mapping {name -> Processor} for registered processors.
    registered = {p.name: p for p in self.processors}
    # Figure out what processors weren't run yet.
    to_run = [registered[p] for p in processors if p in inst.processors_pending]

    # Helper function that updates PackageInstance and ProcessingResult.
    @ndb.transactional
    def store_result(processor_name, result, error):
      # Only one must be set.
      assert (result is None) != (error is None), (result, error)
      # Do not ever overwrite any existing results.
      key = processing_result_key(package_name, instance_id, processor_name)
      if key.get():  # pragma: no cover
        return
      # Update package instance's processors_* fields.
      package_instance = package_instance_key(package_name, instance_id).get()
      assert package_instance
      assert processor_name in package_instance.processors_pending
      assert processor_name not in package_instance.processors_success
      assert processor_name not in package_instance.processors_failure
      package_instance.processors_pending.remove(processor_name)
      if result is not None:
        package_instance.processors_success.append(processor_name)
      else:
        package_instance.processors_failure.append(processor_name)
      # Prepare the ProcessingResult entity.
      result_entity = ProcessingResult(key=key, created_ts=utils.utcnow())
      result_entity.success = result is not None
      result_entity.result = result
      result_entity.error = error
      # Apply the change.
      ndb.put_multi([package_instance, result_entity])

    # Run the processing.
    data = reader.PackageReader(self.cas_service, DIGEST_ALGO, instance_id)
    try:
      for proc in to_run:
        logging.info(
            'Running processor "%s" on %s:%s',
            proc.name, package_name, instance_id)
        try:
          store_result(proc.name, proc.run(inst, data), None)
        # Let any other exception to propagate to task queue wrapper.
        except (processing.ProcessingError, reader.ReaderError) as exc:
          logging.error(
              'Processor "%s" failed.\nInstance: %s:%s\n\n%s',
              proc.name, package_name, instance_id, exc)
          store_result(proc.name, None, str(exc))
    finally:
      data.close()

  def _register_package(self, package_name, caller, now=None):
    """Implementation of register_package, see its docstring.

    Expected to be called in a transaction. Reused from register_instance.
    """
    assert ndb.in_transaction()
    key = package_key(package_name)
    pkg = key.get()
    if pkg:
      return pkg, False
    pkg = Package(
        key=key,
        registered_by=caller,
        registered_ts=now or utils.utcnow())
    pkg.put()
    return pkg, True


def is_valid_package_path(package_name):
  """True if string looks like a valid package name."""
  return bool(PACKAGE_NAME_RE.match(package_name))


def is_valid_instance_id(instance_id):
  """True if string looks like a valid package instance ID."""
  return cas.is_valid_hash_digest(DIGEST_ALGO, instance_id)


def get_repo_service():
  """Factory method that returns configured RepoService instance.

  If the service is not configured, returns None. Also acts as a mocking point
  for unit tests.
  """
  cas_service = cas.get_cas_service()
  if not cas_service:  # pragma: no cover
    return None
  return RepoService(
      cas_service=cas_service,
      processors=[client.ExtractCIPDClientProcessor(cas_service)])


################################################################################
## Core entities.


class Package(ndb.Model):
  """Entity root for PackageInstance entities for some particular package.

  Id is a package name.
  """
  # Who registered the package.
  registered_by = auth.IdentityProperty()
  # When the package was registered.
  registered_ts = ndb.DateTimeProperty()

  @property
  def package_name(self):
    """Name of the package."""
    return self.key.string_id()


class PackageInstance(ndb.Model):
  """Represents some uploaded package instance.

  ID is package instance ID (SHA1 hex digest of package body).
  Parent entity is Package(id=package_name).
  """
  # Who registered the instance.
  registered_by = auth.IdentityProperty()
  # When the instance was registered.
  registered_ts = ndb.DateTimeProperty()

  # Names of processors scheduled for an instance or currently running.
  processors_pending = ndb.StringProperty(repeated=True)
  # Names of processors that successfully finished the processing.
  processors_success = ndb.StringProperty(repeated=True)
  # Names of processors that returned fatal error.
  processors_failure = ndb.StringProperty(repeated=True)

  @property
  def package_name(self):
    """Name of the package this instance belongs to."""
    return self.key.parent().string_id()

  @property
  def instance_id(self):
    """Package instance ID (SHA1 of package file content)."""
    return self.key.string_id()


def package_key(package_name):
  """Returns ndb.Key corresponding to particular Package entity."""
  assert is_valid_package_path(package_name), package_name
  return ndb.Key(Package, package_name)


def package_instance_key(package_name, instance_id):
  """Returns ndb.Key corresponding to particular PackageInstance."""
  assert is_valid_instance_id(instance_id), instance_id
  return ndb.Key(PackageInstance, instance_id, parent=package_key(package_name))


################################################################################
## Package processing (see also cipd/processing.py).


class ProcessingResult(ndb.Model):
  """Contains information extracted from the package instance file.

  Gets extracted in an asynchronous post processing step triggered after
  the instance is uploaded. Immutable.

  Entity ID is a processor name used to extract it. Parent entity is
  PackageInstance the information was extracted from.
  """
  # When the entity was created.
  created_ts = ndb.DateTimeProperty()
  # True if finished successfully, False if failed.
  success = ndb.BooleanProperty(required=True)
  # For success==False, an error message.
  error = ndb.TextProperty(required=False)
  # For success==True, a result of the processing as returned by Processor.run.
  result = ndb.JsonProperty(required=False, compressed=True)


def processing_result_key(package_name, instance_id, processor_name):
  """Returns ndb.Key of ProcessingResult entity."""
  assert isinstance(processor_name, str), processor_name
  return ndb.Key(
      ProcessingResult, processor_name,
      parent=package_instance_key(package_name, instance_id))


################################################################################
## Task queues.


class ProcessTaskQueueHandler(webapp2.RequestHandler):  # pragma: no cover
  """Runs package instance post processing steps."""
  # pylint: disable=R0201
  @decorators.silence(
      datastore_errors.InternalError,
      datastore_errors.Timeout,
      datastore_errors.TransactionFailedError,
      runtime.DeadlineExceededError)
  @decorators.require_taskqueue('cipd-process')
  def post(self, instance_id):
    service = get_repo_service()
    if service is None:
      self.abort(500, detail='Repo service is misconfigured')
    payload = json.loads(self.request.body)
    if payload['instance_id'] != instance_id:
      logging.error('Bad cipd-process task, mismatching instance_id')
      return
    service.process_instance(
        package_name=payload['package_name'],
        instance_id=payload['instance_id'],
        processors=payload['processors'])


def get_backend_routes():  # pragma: no cover
  """Returns a list of webapp2.Route to add to backend WSGI app."""
  return [
    webapp2.Route(
        r'/internal/taskqueue/cipd-process/<instance_id:.+>',
        ProcessTaskQueueHandler),
  ]
