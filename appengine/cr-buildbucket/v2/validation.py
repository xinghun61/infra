# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validates V2 proto messages.

Internally, this module is a bit magical. It keeps a stack of fields currently
being validated per thread. It is used to construct a path to an invalid field
value.
"""

import contextlib
import re
import threading

import buildtags
import errors


class Error(Exception):
  """Raised on validation errors."""


################################################################################
# Validation of common.proto messages.
# The order of functions must match the order of messages in common.proto.


def validate_gerrit_change(change):
  """Validates common_pb2.GerritChange."""
  # project is not required.
  _check_truth(change, 'host', 'change', 'patchset')


def validate_gitiles_commit(commit):
  """Validates common_pb2.GitilesCommit."""
  _check_truth(commit, 'host', 'project')
  if not commit.id and not commit.ref:
    _err('id or ref is required')
  if commit.id:
    with _enter('id'):
      _validate_hex_sha1(commit.id)
  if commit.ref:
    if not commit.ref.startswith('refs/'):
      _enter_err('ref', 'must start with "refs/"')
  if commit.position and not commit.ref:
    _err('position requires ref')


def validate_tags(string_pairs, mode):
  """Validates a list of common.StringPair tags.

  For mode, see buildtags.validate_tags docstring.
  """
  for p in string_pairs:
    if ':' in p.key:
      _err('tag key "%s" cannot have a colon', p.key)

  try:
    tags = ['%s:%s' % (p.key, p.value) for p in string_pairs]
    buildtags.validate_tags(tags, mode)
  except errors.InvalidInputError as ex:
    _err(ex.message)


################################################################################
# Validation of build.proto messages.
# The order of functions must match the order of messages in common.proto.


def validate_builder_id(builder_id):
  """Validates build_pb2.BuilderID."""
  _check_truth(builder_id, 'project', 'bucket', 'builder')


################################################################################
# Validation of rpc.proto messages.
# The order of functions must match the order of messages in common.proto.


def validate_get_build_request(req):
  """Validates rpc_pb2.GetBuildRequest."""
  if req.id:
    if req.HasField('builder') or req.build_number:
      _err('id is mutually exclusive with builder and build_number')
  elif req.HasField('builder') and req.build_number:
    validate_builder_id(req.builder)
  else:
    _err('id or (builder and build_number) are required')


def validate_search_builds_request(req):
  """Validates rpc_pb2.SearchBuildRequest."""
  with _enter('predicate'):
    validate_build_predicate(req.predicate)
  _validate_paged_request(req)


def validate_build_predicate(predicate):
  """Validates rpc_pb2.BuildPredicate."""
  if predicate.HasField('builder'):
    with _enter('builder'):
      validate_builder_id(predicate.builder)

  _check_repeated(predicate, 'gerrit_changes', validate_gerrit_change)

  if predicate.HasField('output_gitiles_commit'):
    with _enter('output_gitiles_commit'):
      _validate_predicate_output_gitiles_commit(predicate.output_gitiles_commit)

  if predicate.HasField('create_time') and predicate.HasField('build'):
    _err('create_time and build are mutually exclusive')

  with _enter('tags'):
    validate_tags(predicate.tags, 'search')


# List of supported BuildPredicate.output_gitiles_commit field sets.
# It is more restrictied than the generic validate_gitiles_commit because the
# field sets by which builds are indexed are more restricted.
SUPPORTED_PREDICATE_OUTPUT_GITILES_COMMIT_FIELD_SET = {
    tuple(sorted(s)) for s in [
        ('host', 'project', 'id'),
        ('host', 'project', 'ref'),
        ('host', 'project', 'ref', 'position'),
    ]
}


def _validate_predicate_output_gitiles_commit(commit):
  """Validates BuildsPredicate.output_gitiles_commit.

  From rpc_pb2.SearchBuildsRequest.output_gitiles_commit comment:
    One of the following subfield sets must specified:
    - host, project, id
    - host, project, ref
    - host, project, ref, position
  """
  field_set = tuple(sorted(f.name for f, _ in commit.ListFields()))
  if field_set not in SUPPORTED_PREDICATE_OUTPUT_GITILES_COMMIT_FIELD_SET:
    _err(
        'unsupported set of fields %r. Supported field sets: %r', field_set,
        SUPPORTED_PREDICATE_OUTPUT_GITILES_COMMIT_FIELD_SET
    )
  validate_gitiles_commit(commit)


################################################################################
# Internals.


def _validate_hex_sha1(sha1):
  pattern = r'[a-z0-9]{40}'
  if not re.match(pattern, sha1):
    _err('does not match r"%s"', pattern)


def _validate_paged_request(req):
  """Validates req.page_size."""
  if req.page_size < 0:
    _enter_err('page_size', 'must be not be negative')


def _check_truth(msg, *field_names):
  """Validates that the field values are truish."""
  for f in field_names:
    if not getattr(msg, f):
      _enter_err(f, 'required')


def _check_repeated(msg, field_name, validator):
  """Validates each element of a repeated field."""
  for i, c in enumerate(getattr(msg, field_name)):
    with _enter('%s[%d]' % (field_name, i)):
      validator(c)


@contextlib.contextmanager
def _enter(name):
  _field_stack().append(name)
  try:
    yield
  finally:
    _field_stack().pop()


def _err(fmt, *args):
  field_path = '.'.join(_field_stack())
  raise Error('%s: %s' % (field_path, fmt % args))


def _enter_err(name, fmt, *args):
  with _enter(name):
    _err(fmt, *args)


def _field_stack():
  if not hasattr(_CONTEXT, 'field_stack'):  # pragma: no cover
    _CONTEXT.field_stack = []
  return _CONTEXT.field_stack


# Validation context of the current thread.
_CONTEXT = threading.local()
