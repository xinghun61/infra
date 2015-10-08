# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implementation of package repository service.

Package and PackageInstance
---------------------------

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

Refs
----
A package can have any number of 'refs'. A ref is a named pointer to some
existing PackageInstance. For example package "infra/tools/cipd" may have a
ref called "stable" that points to currently stable version of the tool.

A ref can point only to fully processed package instance (ones that pass all
processors with success).

Tags
----

Each PackageInstance has a set of key:value pairs assigned to it, called tags.
Examples of tags:
  * git_revision:d42ba1b3df1c911b46fbf8ee217ff53cd207905b
  * buildbot_build:chromium.infra/infra-continuous-trusty-64/115
  * reitveld_cl:1234567
  * ...

The tag key doesn't have to be unique. For example, if two different git
revisions of the source code produce exact same package instance, the instance
would have two git_revision: tags (git_revision:<rev1>, git_revision:<rev2>).

Tags are used in search queries, e.g. "give me package instance that corresponds
to a given git revision".

Only fully processed package instance (ones that pass all processors with
success) can be tagged, since tagging a package makes it discoverable in
the search.

TODO(vadimsh): Support unique tags (i.e. only one package instance can be
tagged with such tag)? For example, tags with keys that start with '@' can be
unique: "@release:0.1". The difference from ref is mostly in semantics: unique
tags aren't supposed to be moved (i.e. detached and attached again).

Access Control
--------------

Package namespace is a file-system like hierarchical structure where each node
has an access control list inherited by all subnodes. ACL for some subpath
contains a list of pairs (group | user, role) where possible roles are:
  * READER - can fetch package instances.
  * WRITER - same as READER + can register new packages and instances.
  * OWNER - same as WRITER + can view and change ACLs for subpaths.

ACLs of a leaf package is a union of ACLs of all parent nodes. Exclusions or
overrides are not supported.

ACL changes are applied atomically (e.g. multiple ACLs can be changed all at
once or none at all), but checks are still only eventually consistent (for
performance and code simplicity).

TODO(vadimsh): Add fine grained ACL for tags and refs. Tags that are set by
Buildbot builders should not be allowed to set by other WRITERs.
"""

import collections
import hashlib
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

# Regular expression for a package path (path inside package namespace).
PACKAGE_PATH_RE = re.compile(r'^([a-z0-9_\-]+/)*[a-z0-9_\-]+$')

# Regular expression for a package reference name.
REF_RE = re.compile(r'^[a-z0-9_\-]{1,100}$')

# Maximum length of the tag (key + value).
TAG_MAX_LEN = 400

# Regular expression for a valid tag key.
TAG_KEY_RE = re.compile(r'^[a-z0-9_\-]+$')

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

  @ndb.transactional
  def delete_package(self, package_name):
    """Deletes a package along with all its instances.

    Very nuclear method. Removes all associated metadata (refs, tags). There's
    no undo. Note that actual package files are left in the CAS storage since
    there's no garbage collection mechanism there yet.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.

    Returns:
      True if deleted something, False if already gone.
    """
    # TODO(vadimsh): This would probably exceed transaction size limit for huge
    # packages with lots of instances.
    assert is_valid_package_name(package_name), package_name
    root_key = package_key(package_name)
    queries = [
      PackageInstance.query(ancestor=root_key),
      PackageRef.query(ancestor=root_key),
      InstanceTag.query(ancestor=root_key),
      ProcessingResult.query(ancestor=root_key),
    ]
    futures = [q.fetch_async(keys_only=True) for q in queries]
    keys_to_delete = [root_key]
    for f in futures:
      keys_to_delete.extend(f.get_result())
    # Proceed with deleting even if len(keys_to_delete) == 1. It covers the case
    # of packages with no instances. It impossible with current version of API,
    # but was possible before and there are few such packages in the datastore.
    logging.warning('Deleting %d entities', len(keys_to_delete))
    ndb.delete_multi(keys_to_delete)
    return len(keys_to_delete) > 1

  @staticmethod
  def _is_in_directory(directory, path, recursive):
    """Tests if the path is under the given directory.

    This assumes directory is a prefix of path.

    Args:
      directory: string, directory the path should fall under.
      path: string, full path to test.
      recursive: whether the path can be in a subdirectory.

    Returns:
      True if the path is under the directory.
    """
    start = len(directory)

    # The directory itself or anything shorter is not a match.
    if len(path) <= start:
      return False

    # The root doesn't begin with slash so only check non-root searches.
    if start:
      if path[start] != '/':
        return False
      start += 1

    # A subdirectory was found and we're not looking for recursive matches.
    if not recursive and '/' in path[start:]:
      return False
    return True

  def list_packages(self, dir_path, recursive):
    """Returns lists of package names and directory names with the given prefix.

    Args:
      dir_path: string directory from which to list packages.
      recursive: boolean whether to list contents of subdirectories.

    Returns:
      [package name, ...], [directory name, ...]
    """
    query = Package.query()

    # Normalize directory to simplify matching logic later.
    dir_path = dir_path.rstrip('/')

    # Only apply the filtering if a prefix was given. The empty string isn't a
    # valid key and will result in an exception.
    if dir_path:
      query = query.filter(
          # Prefix match using the operators available to us. Packages can only
          # contain lowercase ascii, numbers, and '/' so '\uffff' will always
          # be larger.
          ndb.AND(Package.key >= ndb.Key(Package, dir_path),
                  Package.key <= ndb.Key(Package, dir_path + u'\uffff')))
    pkgs = []
    dirs = set()
    for key in query.iter(keys_only=True):
      pkg = key.string_id()

      # In case the index is stale since this is an eventual consistent query.
      if not pkg.startswith(dir_path):  # pragma: no cover
        continue
      pkgs.append(pkg)

      # Add in directories derived from full package path.
      if '/' in pkg:
        parts = pkg.split('/')
        dirs.update('/'.join(parts[:n]) for n in xrange(1, len(parts)))

    dirs = [d for d in dirs if self._is_in_directory(dir_path, d, recursive)]
    pkgs = [p for p in pkgs if self._is_in_directory(dir_path, p, recursive)
            or len(dir_path) == len(p)]
    return pkgs, dirs

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
    # Is PackageInstance already registered?
    key = package_instance_key(package_name, instance_id)
    inst = key.get()
    if inst is not None:
      return inst, False

    # Register Package entity if missing.
    now = now or utils.utcnow()
    pkg_key = package_key(package_name)
    if not pkg_key.get():
      Package(key=pkg_key, registered_by=caller, registered_ts=now).put()

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

  @ndb.transactional
  def set_package_ref(self, package_name, ref, instance_id, caller, now=None):
    """Creates or moves a package reference to point to an existing instance.

    Idempotent. Package instance must exist and must have all processors
    successfully finished.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      ref: name of the reference, e.g. 'stable'.
      instance_id: identifier of the package instance (SHA1 of package file).
      caller: auth.Identity that issued the request.
      now: datetime when the request was made (or None for current time).

    Returns:
      PackageRef instance.
    """
    # TODO(vadimsh): Write performed actions into some audit log.
    assert is_valid_package_ref(ref), ref
    self._assert_instance_is_ready(package_name, instance_id)

    # Do not overwrite existing timestamp if ref is already set as needed.
    key = package_ref_key(package_name, ref)
    ref = key.get() or PackageRef(key=key)
    if ref.instance_id != instance_id:
      ref.instance_id = instance_id
      ref.modified_by = caller
      ref.modified_ts = now or utils.utcnow()
      ref.put()
    return ref

  def get_package_refs(self, package_name, refs):
    """Fetches information about given package refs.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      refs: list of strings with refs to look for.

    Returns:
      {ref: corresponding PackageRef or None if not set}.
    """
    assert is_valid_package_name(package_name), package_name
    assert refs and all(is_valid_package_ref(ref) for ref in refs), refs
    entities = ndb.get_multi(package_ref_key(package_name, ref) for ref in refs)
    return dict(zip(refs, entities))

  def query_package_refs(self, package_name):
    """Lists all refs belonging to a package (sorted by creation time).

    Newest refs first.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).

    Returns:
      List of PackageRef instances.
    """
    assert is_valid_package_name(package_name), package_name
    q = PackageRef.query(ancestor=package_key(package_name))
    q = q.order(-PackageRef.modified_ts)
    return q.fetch()

  def query_instance_refs(self, package_name, instance_id):
    """Lists all refs pointing to a package instance sorted by creation time.

    Newest refs first.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).

    Returns:
      List of PackageRef instances.
    """
    assert is_valid_package_name(package_name), package_name
    assert is_valid_instance_id(instance_id), instance_id
    q = PackageRef.query(
        PackageRef.instance_id == instance_id,
        ancestor=package_key(package_name))
    q = q.order(-PackageRef.modified_ts)
    return q.fetch()

  def query_tags(self, package_name, instance_id):
    """Lists all tags attached to a package instance sorted by creation time.

    Newest tags first.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).

    Returns:
      List of InstanceTag instances.
    """
    # TODO(vadimsh): Support cursors.
    assert is_valid_package_name(package_name), package_name
    assert is_valid_instance_id(instance_id), instance_id
    q = InstanceTag.query(
        ancestor=package_instance_key(package_name, instance_id))
    q = q.order(-InstanceTag.registered_ts)
    return q.fetch()

  def get_tags(self, package_name, instance_id, tags):
    """Fetches information about given instance tags.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      tags: list of strings with tags to look for.

    Returns:
      {tag: corresponding InstanceTag or None if not attached}.
    """
    assert is_valid_package_name(package_name), package_name
    assert is_valid_instance_id(instance_id), instance_id
    assert tags and all(is_valid_instance_tag(tag) for tag in tags), tags
    attached = ndb.get_multi(
        instance_tag_key(package_name, instance_id, tag)
        for tag in tags)
    return dict(zip(tags, attached))

  @ndb.transactional
  def attach_tags(self, package_name, instance_id, tags, caller, now=None):
    """Adds a bunch of tags to an existing package instance.

    Idempotent. Skips existing tags. Package instance must exist and must have
    all processors successfully finished.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      tags: list of strings with tags to attach.
      caller: auth.Identity that issued the request.
      now: datetime when the request was made (or None for current time).

    Returns:
      {tag: corresponding InstanceTag (just created or existing one)}.
    """
    assert tags and all(is_valid_instance_tag(tag) for tag in tags), tags
    self._assert_instance_is_ready(package_name, instance_id)

    # Grab info about existing tags, register new ones.
    now = now or utils.utcnow()
    existing = ndb.get_multi(
        instance_tag_key(package_name, instance_id, tag)
        for tag in tags)
    to_create = [
      InstanceTag(
          key=instance_tag_key(package_name, instance_id, tag),
          tag=tag,
          registered_by=caller,
          registered_ts=now)
      for tag, ent in zip(tags, existing) if not ent
    ]
    ndb.put_multi(to_create)

    attached = {}
    attached.update({e.tag: e for e in existing if e})
    attached.update({e.tag: e for e in to_create})
    return attached

  @ndb.transactional
  def detach_tags(self, package_name, instance_id, tags):
    """Detaches given tags from a package instance.

    Idempotent. Skips missing tags.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
      tags: list of strings with tags to detach.
    """
    # TODO(vadimsh): Write performed actions into some audit log.
    assert tags and all(is_valid_instance_tag(tag) for tag in tags), tags
    ndb.delete_multi(
        instance_tag_key(package_name, instance_id, tag)
        for tag in tags)

  def search_by_tag(self, tag, package_name=None, callback=None):
    """Returns package instances with a given tag.

    Sorts by tagging time. Newest tags first.

    Args:
      tag: tag to search for.
      package_name: if given, limit search only to given package.
      callback: called as callback(package_name, instance_id), returns True to
          continue processing the instance, False to skip. Used to plug in ACLs.

    Returns:
      List of PackageInstance entities.
    """
    # TODO(vadimsh): Support cursors.
    assert is_valid_instance_tag(tag), tag
    q = InstanceTag.query(
        InstanceTag.tag == tag,
        ancestor=package_key(package_name) if package_name else None)
    q = q.order(-InstanceTag.registered_ts)
    found = []
    for tag_key in q.iter(keys_only=True):
      package_name = tag_key.parent().parent().string_id()
      instance_id = tag_key.parent().string_id()
      if callback and not callback(package_name, instance_id):
        continue
      # TODO(vadimsh): This can be fetched asynchronously while next page of
      # query results is being fetched.
      inst = tag_key.parent().get()
      if inst is None:  # pragma: no cover
        continue
      assert isinstance(inst, PackageInstance), inst
      found.append(inst)
    return found

  def resolve_version(self, package_name, version, limit):
    """Given an instance ID, a ref or a tag returns instance IDs that match it.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      version: version to resolve.
      limit: maximum number of matching instance IDs to return.

    Returns:
      List of instance IDs (not ordered).
    """
    assert is_valid_instance_version(version), version

    # Instance ID is already provided as input? Ensure the instance exists.
    if is_valid_instance_id(version):
      inst = self.get_instance(package_name, version)
      return [inst.instance_id] if inst else []

    # A ref? set_package_ref ensures the instance exists, no need to recheck it.
    if is_valid_package_ref(version):
      ref = package_ref_key(package_name, version).get()
      return [ref.instance_id] if ref else []

    # If looks like a tag, resolve it to a list of instance IDs.
    if is_valid_instance_tag(version):
      q = InstanceTag.query(
          InstanceTag.tag == version,
          ancestor=package_key(package_name))
      return [
        k.parent().string_id()
        for k in q.iter(keys_only=True, limit=limit)
      ]

    raise AssertionError('Impossible state')

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

  def _assert_instance_is_ready(self, package_name, instance_id):
    """Asserts that instance can be used to attach tags or point a ref to it.

    Instance must exist and all its processors must finish successfully.

    Args:
      package_name: name of the package, e.g. 'infra/tools/cipd'.
      instance_id: identifier of the package instance (SHA1 of package file).
    """
    inst = package_instance_key(package_name, instance_id).get()
    assert inst, 'Instance doesn\'t exist: %s' % instance_id
    if inst.processors_failure:
      raise AssertionError(
          'Some processors failed for instance %s: %s' %
          (instance_id, ' '.join(inst.processors_failure)))
    if inst.processors_pending:
      raise AssertionError(
          'Some processors are not finished yet for instance %s: %s' %
          (instance_id, ' '.join(inst.processors_pending)))


def is_valid_package_name(package_name):
  """True if string looks like a valid package name."""
  return package_name and bool(PACKAGE_NAME_RE.match(package_name))


def is_valid_package_path(package_path):
  """True if string looks like a valid package path."""
  return package_path and bool(PACKAGE_PATH_RE.match(package_path))


def is_valid_package_ref(ref):
  """True if string looks like a valid ref name."""
  return ref and not is_valid_instance_id(ref) and bool(REF_RE.match(ref))


def is_valid_instance_id(instance_id):
  """True if string looks like a valid package instance ID."""
  return instance_id and cas.is_valid_hash_digest(DIGEST_ALGO, instance_id)


def is_valid_instance_tag(tag):
  """True if string looks like a valid package instance tag."""
  if not tag or ':' not in tag or len(tag) > TAG_MAX_LEN:
    return False
  # Care only about the key. Value can be anything (including empty string).
  return bool(TAG_KEY_RE.match(tag.split(':', 1)[0]))


def is_valid_instance_version(version):
  """True if string looks like an instance ID or a ref, or a tag."""
  return (
      is_valid_instance_id(version) or
      is_valid_package_ref(version) or
      is_valid_instance_tag(version))


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
## Refs support.


class PackageRef(ndb.Model):
  """A named reference to some instance ID.

  ID is a reference name, parent entity is corresponding Package.
  """
  # PackageInstance the ref points to.
  instance_id = ndb.StringProperty()
  # Who added or moved this reference.
  modified_by = auth.IdentityProperty()
  # When the reference was created or moved.
  modified_ts = ndb.DateTimeProperty()

  @property
  def package_name(self):
    """Name of the package this ref belongs to."""
    return self.key.parent().string_id()

  @property
  def ref(self):
    """Name of the ref (extracted from entity key)."""
    return self.key.string_id()


def package_ref_key(package_name, ref):
  """Returns ndb.Key corresponding to particular PackageRef."""
  assert is_valid_package_ref(ref), ref
  return ndb.Key(PackageRef, ref, parent=package_key(package_name))


################################################################################
## Tags support.


class InstanceTag(ndb.Model):
  """Single tag of some package instance.

  ID is hex-encoded SHA1 of the tag. Parent entity is corresponding
  PackageInstance. The tag can't be made a part of the key because total key
  length (including class names, all parent keys) is limited to 500 characters.
  Tags can be pretty long.

  Tags are separate entities (rather than repeated field in PackageInstance) for
  two reasons:
    * There can be many tags attached to an instance (e.g. 'git_revision:...'
      tags for a package that doesn't change between revisions).
    * PackageInstance entity is fetched pretty often, no need to pull all tags
      all the time.
  """
  # The tag itself, as key:value string.
  tag = ndb.StringProperty()
  # Who added this tag.
  registered_by = auth.IdentityProperty()
  # When the tag was added.
  registered_ts = ndb.DateTimeProperty()

  @property
  def package_name(self):
    """Name of the package this tag belongs to."""
    return self.key.parent().parent().string_id()

  @property
  def instance_id(self):
    """Package instance ID this tag belongs to."""
    return self.key.parent().string_id()


def instance_tag_key(package_name, instance_id, tag):
  """Returns ndb.Key corresponding to particular InstanceTag entity."""
  assert is_valid_instance_tag(tag), tag
  return ndb.Key(
      InstanceTag,
      hashlib.sha1(tag).hexdigest(),
      parent=package_instance_key(package_name, instance_id))


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
