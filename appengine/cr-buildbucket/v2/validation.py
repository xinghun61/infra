# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validates V2 proto messages.

Internally, this module is a bit magical. It keeps a stack of fields currently
being validated per thread. It is used to construct a path to an invalid field
value.
"""

import contextlib
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
  _check_fields_truth(change, ('host', 'change', 'patchset'))


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
  """Validates build_pb2.Builder.ID."""
  _check_fields_truth(builder_id, ('project', 'bucket', 'builder'))


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

  if not predicate.HasField('builder') and not predicate.gerrit_changes:
    _err('builder or gerrit_changes is required')

  with _enter('tags'):
    validate_tags(predicate.tags, 'search')


################################################################################
# Internals.

def _validate_paged_request(req):
  """Validates req.page_size."""
  if req.page_size < 0:
    _enter_err('page_size', 'must be not be negative')


def _check_fields_truth(msg, field_names):
  """Validates that the field values are truish."""
  for f in field_names:
    if not getattr(msg, f):
      _enter_err(f, 'not specified')


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
  if not hasattr(_CONTEXT, 'field_stack'):
    _CONTEXT.field_stack = []
  return _CONTEXT.field_stack


# Validation context of the current thread.
_CONTEXT = threading.local()
