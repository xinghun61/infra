# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validates V2 proto messages.

Internally, this module is a bit magical. It keeps a stack of fields currently
being validated per thread. It is used to construct a path to an invalid field
value.
"""

import contextlib
import logging
import re
import threading

from components import cipd

from proto import common_pb2

import buildtags
import config
import errors
import model


class Error(Exception):
  """Raised on validation errors."""


PUBSUB_USER_DATA_MAX_LENGTH = 4096

# Maximum size of Build.summary_markdown field. Defined in build.proto.
MAX_BUILD_SUMMARY_MARKDOWN_SIZE = 4000  # 4 KB

# swarming.py and api.py reserve these properties.
RESERVED_PROPERTY_PATHS = [
    # Reserved for buildbucket internals.
    ['buildbucket'],
    ['$recipe_engine/buildbucket'],

    # Deprecated in favor of api.buildbucket.builder.builder,
    # https://chromium.googlesource.com/infra/luci/recipes-py/+/master/recipe_modules/buildbucket/api.py
    # Prohibited.
    ['buildername'],

    # Deprecated in favor of api.buildbucket.build_input.gitiles_commit,
    # https://chromium.googlesource.com/infra/luci/recipes-py/+/master/recipe_modules/buildbucket/api.py
    # Prohibited.
    ['branch'],
    ['repository'],

    # Set to const true.
    ['$recipe_engine/runtime', 'is_luci'],

    # Populated from Build.input.experimental.
    ['$recipe_engine/runtime', 'is_experimental'],
]

# Statuses with start time required.
START_TIME_REQUIRED_STATUSES = (
    common_pb2.STARTED,
    common_pb2.SUCCESS,
    common_pb2.FAILURE,
)

# Step statuses, listed from best to worst and if applicable. See
# https://chromium.googlesource.com/infra/luci/luci-go/+/dffd1081b775979aa1c5a8046d9a65adead1cee8/buildbucket/proto/step.proto#75
STATUS_PRECEDENCE = (
    common_pb2.SUCCESS,  # best
    common_pb2.FAILURE,
    common_pb2.INFRA_FAILURE,
    common_pb2.CANCELED,  # worst
)

# Character separating parent from children steps.
STEP_SEP = '|'

################################################################################
# Validation of common.proto messages.
# The order of functions must match the order of messages in common.proto.


def validate_gerrit_change(change, require_project=False):
  """Validates common_pb2.GerritChange."""
  # project is not required.
  _check_truth(change, 'host', 'change', 'patchset')
  if require_project and not change.project:  # pragma: no branch
    # TODO(nodir): escalate to an error.
    logging.warning('gerrit_change.project is not specified')


def validate_gitiles_commit(commit, require_ref=True):
  """Validates common_pb2.GitilesCommit."""
  _check_truth(commit, 'host', 'project')

  if require_ref:
    _check_truth(commit, 'ref')
  if commit.ref:
    if not commit.ref.startswith('refs/'):
      _enter_err('ref', 'must start with "refs/"')
  else:
    if not commit.id:
      _err('id or ref is required')
    if commit.position:
      _enter_err('position', 'requires ref')

  if commit.id:
    with _enter('id'):
      _validate_hex_sha1(commit.id)


def validate_tags(string_pairs, mode):
  """Validates a list of common.StringPair tags.

  For mode, see buildtags.validate_tags docstring.
  """
  for p in string_pairs:
    if ':' in p.key:
      _err('tag key "%s" cannot have a colon', p.key)

  with _handle_invalid_input_error():
    tags = ['%s:%s' % (p.key, p.value) for p in string_pairs]
    buildtags.validate_tags(tags, mode)


################################################################################
# Validation of build.proto messages.
# The order of functions must match the order of messages in common.proto.


def validate_builder_id(builder_id, require_bucket=True, require_builder=True):
  """Validates build_pb2.BuilderID."""
  assert require_bucket or not require_builder
  _check_truth(builder_id, 'project')
  if require_bucket:
    _check_truth(builder_id, 'bucket')
  if require_builder:
    _check_truth(builder_id, 'builder')

  with _enter('project'), _handle_invalid_input_error():
    config.validate_project_id(builder_id.project)

  with _enter('bucket'), _handle_invalid_input_error():
    if builder_id.bucket:
      config.validate_bucket_name(builder_id.bucket)
      parts = builder_id.bucket.split('.')
      if len(parts) >= 3 and parts[0] == 'luci':
        _err(
            'invalid usage of v1 bucket format in v2 API; use %r instead',
            parts[2]
        )
    elif builder_id.builder:
      _err('required by .builder field')

  with _enter('builder'), _handle_invalid_input_error():
    if builder_id.builder:
      errors.validate_builder_name(builder_id.builder)


################################################################################
# Validation of rpc.proto messages.
# The order of functions must match the order of messages in rpc.proto.


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


def validate_requested_dimension(dim, expiration_support=True):
  """Validates common_pb2.RequestedDimension."""
  _check_truth(dim, 'key', 'value')

  with _enter('key'):
    if dim.key == 'caches':
      _err('"caches" is invalid; define caches instead')
    if dim.key == 'pool':
      _err('"pool" is not allowed')

  with _enter('expiration'):
    if not expiration_support and dim.HasField('expiration'):
      _err('not supported')

    with _enter('seconds'):
      if dim.expiration.seconds < 0:
        _err('must not be negative')
      if dim.expiration.seconds % 60 != 0:
        _err('must be a multiple of 60')

    if dim.expiration.nanos:
      _enter_err('nanos', 'must be 0')


def validate_schedule_build_request(
    req,
    require_builder=True,
    allow_reserved_properties=False,
):
  if '/' in req.request_id:  # pragma: no cover
    _enter_err('request_id', 'must not contain /')

  if not req.HasField('builder') and not req.template_build_id:
    _err('builder or template_build_id is required')

  if req.HasField('builder'):
    with _enter('builder'):
      validate_builder_id(req.builder, require_builder=require_builder)

  with _enter('exe'):
    _check_falsehood(req.exe, 'cipd_package')
    if req.exe.cipd_version:
      with _enter('cipd_version'):
        _validate_cipd_version(req.exe.cipd_version)

  with _enter('properties'):
    validate_struct(req.properties)
    if not allow_reserved_properties:  # pragma: no branch
      for path in RESERVED_PROPERTY_PATHS:
        if _struct_has_path(req.properties, path):
          _err('property path %r is reserved', path)

  if req.HasField('gitiles_commit'):
    with _enter('gitiles_commit'):
      validate_gitiles_commit(req.gitiles_commit)

  _check_repeated(
      req, 'gerrit_changes',
      lambda c: validate_gerrit_change(c, require_project=True)
  )

  with _enter('tags'):
    validate_tags(req.tags, 'new')

  # TODO(crbug.com/926538): add support for dimension expiration
  _check_repeated(
      req, 'dimensions',
      lambda d: validate_requested_dimension(d, expiration_support=False)
  )

  key_exp = set()
  with _enter('dimensions'):
    for d in req.dimensions:
      t = (d.key, d.expiration.seconds)
      if t in key_exp:
        _err(
            'key "%s" and expiration %ds are not unique', d.key,
            d.expiration.seconds
        )
      key_exp.add(t)

  if req.priority < 0 or req.priority > 255:
    _enter_err('priority', 'must be in [0, 255]')

  if req.HasField('notify'):  # pragma: no branch
    with _enter('notify'):
      validate_notification_config(req.notify)


def validate_cancel_build_request(req):
  _check_truth(req, 'id', 'summary_markdown')
  with _enter('summary_markdown'):
    validate_build_summary_markdown(req.summary_markdown)


def validate_struct(struct):
  for name, value in struct.fields.iteritems():
    if not value.WhichOneof('kind'):
      _enter_err(name, 'value is not set; for null, initialize null_value')


def validate_notification_config(notify):
  _check_truth(notify, 'pubsub_topic')
  if len(notify.user_data) > PUBSUB_USER_DATA_MAX_LENGTH:
    _enter_err('user_data', 'must be <= %d bytes', PUBSUB_USER_DATA_MAX_LENGTH)


# Set of UpdateBuildRequest field paths updatable via UpdateBuild RPC.
UPDATE_BUILD_FIELD_PATHS = {
    'build.status',
    'build.status_details',
    'build.summary_markdown',
    'build.steps',
    'build.output.properties',
    'build.output.gitiles_commit',
}
# Set of valid build statuses supported by UpdateBuild RPC.
UPDATE_BUILD_STATUSES = {
    common_pb2.STARTED,
    # kitchen does not actually use SUCCESS. It relies on swarming pubsub
    # handler in Buildbucket because a task may fail after recipe succeeded.
    common_pb2.SUCCESS,
    common_pb2.FAILURE,
    common_pb2.INFRA_FAILURE,
}


def validate_update_build_request(req, build_steps=None):
  """Validates rpc_pb2.UpdateBuildRequest.

  build_steps is prepared model.BuildSteps corresponding to req.build.steps.
  If None, then validate_update_build_request will serialize potentially large
  req.build.steps.
  """
  update_paths = set(req.update_mask.paths)
  with _enter('update_mask', 'paths'):
    unsupported = update_paths - UPDATE_BUILD_FIELD_PATHS
    if unsupported:
      _err('unsupported path(s) %r', sorted(unsupported))

  # Check build values, if present in the mask.
  with _enter('build'):
    with _enter('id'):
      _check_truth(req.build.id)

    if 'build.status' in update_paths:
      if req.build.status not in UPDATE_BUILD_STATUSES:
        _enter_err(
            'status', 'invalid status %s for UpdateBuild',
            common_pb2.Status.Name(req.build.status)
        )

    if 'build.output.gitiles_commit' in update_paths:
      with _enter('output', 'gitiles_commit'):
        validate_gitiles_commit(req.build.output.gitiles_commit)

    if 'build.summary_markdown' in update_paths:
      with _enter('summary_markdown'):
        validate_build_summary_markdown(req.build.summary_markdown)

    if 'build.output.properties' in update_paths:
      with _enter('output', 'properties'):
        validate_struct(req.build.output.properties)

    if 'build.steps' in update_paths:  # pragma: no branch
      with _enter('steps'):
        build_steps = build_steps or model.BuildSteps.make(req.build)
        limit = model.BuildSteps.MAX_STEPS_LEN
        if len(build_steps.step_container_bytes) > limit:
          _err('too big to accept')

        validate_steps(req.build.steps)


def validate_build_summary_markdown(summary_markdown):
  size = len(summary_markdown)
  limit = MAX_BUILD_SUMMARY_MARKDOWN_SIZE
  if size > limit:
    _err('too big to accept (%d > %d bytes)', size, limit)


def validate_steps(steps):
  seen_steps = dict()
  for i, s in enumerate(steps):
    with _enter('step[%d]' % i):
      validate_step(s, seen_steps)


def validate_step(step, steps):
  """Validates build's step, internally and relative to (previous) steps."""

  _check_truth(step, 'name')
  if step.name in steps:
    _enter_err('name', 'duplicate: %r', step.name)

  validate_internal_timing_consistency(step)

  log_names = set()
  _check_repeated(step, 'logs', lambda log: validate_log(log, log_names))

  name_path = step.name.split(STEP_SEP)
  parent_name = STEP_SEP.join(name_path[:-1])
  if parent_name:
    if parent_name not in steps:
      _err('parent to %r must precede', step.name)
    parent = steps[parent_name]

    validate_status_consistency(step, parent)
    validate_timing_consistency(step, parent)

  steps[step.name] = step


def validate_internal_timing_consistency(step):
  """Validates internal timing consistency of a step."""

  if (step.status not in common_pb2.Status.values() or
      step.status == common_pb2.STATUS_UNSPECIFIED):
    _err('must have buildbucket.v2.Status that is not STATUS_UNSPECIFIED')

  if step.status in START_TIME_REQUIRED_STATUSES and not step.HasField(
      'start_time'):
    _enter_err(
        'start_time', 'required by status %s',
        common_pb2.Status.Name(step.status)
    )
  elif step.status < common_pb2.STARTED and step.HasField('start_time'):
    _enter_err(
        'start_time', 'invalid for status %s',
        common_pb2.Status.Name(step.status)
    )

  if bool(step.status & common_pb2.ENDED_MASK) ^ step.HasField('end_time'):
    _err('must have both or neither end_time and a terminal status')

  if (step.HasField('end_time') and
      step.start_time.ToDatetime() > step.end_time.ToDatetime()):
    _err('start_time after end_time')


def validate_status_consistency(child, parent):
  """Validates inter-step status consistency."""

  c, p = child.status, parent.status
  c_name, p_name = common_pb2.Status.Name(c), common_pb2.Status.Name(p)

  if p == common_pb2.SCHEDULED:
    _enter_err('status', 'parent %r must be at least STARTED', parent.name)

  if not bool(c & common_pb2.ENDED_MASK) and p != common_pb2.STARTED:
    _enter_err(
        'status', 'non-terminal (%s) %r must have STARTED parent %r (%s)',
        c_name, child.name, parent.name, p_name
    )

  if (p in STATUS_PRECEDENCE and c in STATUS_PRECEDENCE and
      STATUS_PRECEDENCE.index(p) < STATUS_PRECEDENCE.index(c)):
    _enter_err(
        'status', '%r\'s status %s is worse than parent %r\'s status %s',
        child.name, c_name, parent.name, p_name
    )


def validate_timing_consistency(child, parent):
  """Validates inter-step timing consistency."""

  parent_start = parent.start_time.ToDatetime(
  ) if parent.HasField('start_time') else None
  parent_end = parent.end_time.ToDatetime(
  ) if parent.HasField('end_time') else None

  if child.HasField('start_time'):
    child_start = child.start_time.ToDatetime()
    with _enter('start_time'):
      if parent_start and parent_start > child_start:
        _err('cannot precede parent %r\'s start time', parent.name)
      if parent_end and parent_end < child_start:
        _err('cannot follow parent %r\'s end time', parent.name)

  if child.HasField('end_time'):
    child_end = child.end_time.ToDatetime()
    with _enter('end_time'):
      if parent_start and parent_start > child_end:
        _err('cannot precede parent %r\'s start time', parent.name)
      if parent_end and parent_end < child_end:
        _err('cannot follow parent %r\'s end time', parent.name)


def validate_log(log, names):
  """Validates a log within a build step; checks uniqueness against names param.
  """
  _check_truth(log, 'name', 'url', 'view_url')

  if log.name in names:
    _enter_err('name', 'duplicate: %r', log.name)
  names.add(log.name)


def validate_build_predicate(predicate):
  """Validates rpc_pb2.BuildPredicate."""
  if predicate.HasField('builder'):
    with _enter('builder'):
      validate_builder_id(
          predicate.builder, require_bucket=False, require_builder=False
      )

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
  validate_gitiles_commit(commit, require_ref=False)


################################################################################
# Internals.


def _validate_cipd_version(version):
  if not cipd.is_valid_version(version):
    _err('invalid version "%s"', version)


def _struct_has_path(struct, path):
  """Returns True if struct has a value at field path."""
  for p in path:
    f = struct.fields.get(p)
    if f is None:
      return False
    struct = f.struct_value
  return True


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


def _check_falsehood(msg, *field_names):
  """Validates that the field values are falsish."""
  for f in field_names:
    if getattr(msg, f):
      _enter_err(f, 'disallowed')


def _check_repeated(msg, field_name, validator):
  """Validates each element of a repeated field."""
  for i, c in enumerate(getattr(msg, field_name)):
    with _enter('%s[%d]' % (field_name, i)):
      validator(c)


@contextlib.contextmanager
def _enter(*names):
  _field_stack().extend(names)
  try:
    yield
  finally:
    _field_stack()[-len(names):] = []


def _err(fmt, *args):
  field_path = '.'.join(_field_stack())
  raise Error('%s: %s' % (field_path, fmt % args))


@contextlib.contextmanager
def _handle_invalid_input_error():
  try:
    yield
  except errors.InvalidInputError as ex:
    _err('%s', ex.message)


def _enter_err(name, fmt, *args):
  with _enter(name):
    _err(fmt, *args)


def _field_stack():
  if not hasattr(_CONTEXT, 'field_stack'):  # pragma: no cover
    _CONTEXT.field_stack = []
  return _CONTEXT.field_stack


# Validation context of the current thread.
_CONTEXT = threading.local()
