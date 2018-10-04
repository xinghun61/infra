# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=line-too-long

import copy
import json
import re
import string

from components.config import validation

from proto.config import project_config_pb2
from . import flatten_swarmingcfg

_DIMENSION_KEY_RGX = re.compile(r'^[a-zA-Z\_\-]+$')
# Copied from
# https://github.com/luci/luci-py/blob/75de6021b50a73e140eacfb80760f8c25aa183ff/appengine/swarming/server/task_request.py#L101
# Keep it synchronized.
_CACHE_NAME_RE = re.compile(ur'^[a-z0-9_]{1,4096}$')
# See https://chromium.googlesource.com/infra/luci/luci-py/+/master/appengine/swarming/server/service_accounts.py
_SERVICE_ACCOUNT_RE = re.compile(r'^[0-9a-zA-Z_\-\.\+\%]+@[0-9a-zA-Z_\-\.]+$')

BUILDER_NAME_VALID_CHARS = string.ascii_letters + string.digits + '()-_. '
_BUILDER_NAME_VALID_CHAR_SET = frozenset(BUILDER_NAME_VALID_CHARS)


def _validate_hostname(hostname, ctx):
  if not hostname:
    ctx.error('unspecified')
  if '://' in hostname:
    ctx.error('must not contain "://"')


def _validate_service_account(service_account, ctx):
  if (service_account != 'bot' and
      not _SERVICE_ACCOUNT_RE.match(service_account)):
    ctx.error(
        'value "%s" does not match %s', service_account,
        _SERVICE_ACCOUNT_RE.pattern
    )


# The below is covered by swarming_test.py and swarmbucket_api_test.py
def read_dimensions(builder_cfg):  # pragma: no cover
  """Read the dimensions for a builder config.

  This different from flatten_swarmingcfg.parse_dimensions in that this:
  * Factors in the auto_builder_dimensions field.
  * Removes empty value fields.

  Returns:
    dimensions is returned as dict {key: (value, expiration_secs)}.
  """
  dimensions = flatten_swarmingcfg.parse_dimensions(builder_cfg.dimensions)
  if (builder_cfg.auto_builder_dimension == project_config_pb2.YES and
      u'builder' not in dimensions):
    dimensions[u'builder'] = (builder_cfg.name, 0)

  # Remove empty values.
  return {k: (v, exp) for k, (v, exp) in dimensions.iteritems() if v}


def _validate_tag(tag, ctx):
  # a valid swarming tag is a string that contains ":"
  if ':' not in tag:
    ctx.error('does not have ":": %s', tag)
  name = tag.split(':', 1)[0]
  if name.lower() == 'builder':
    ctx.error(
        'do not specify builder tag; '
        'it is added by swarmbucket automatically'
    )


def _validate_dimension_key(key, known_keys, ctx):
  if not key:
    ctx.error('no key')
    return
  if not _DIMENSION_KEY_RGX.match(key):
    ctx.error(
        'key "%s" does not match pattern "%s"', key, _DIMENSION_KEY_RGX.pattern
    )
    return
  if key in known_keys:
    ctx.error('duplicate key %s', key)
    return
  known_keys.add(key)


def _validate_dimensions(field_name, dimensions, ctx):
  known_keys = set()
  expirations = set()
  for i, dim in enumerate(dimensions):
    with ctx.prefix('%s #%d: ', field_name, i + 1):
      parts = dim.split(':', 1)
      if len(parts) != 2:
        ctx.error('does not have ":"')
        continue
      key, value = parts
      expiration_secs = 0
      try:
        expiration_secs = int(key)
      except ValueError:
        pass
      else:
        parts = value.split(':', 1)
        if len(parts) != 2:
          ctx.error('has expiration_secs but missing value')
          continue
        key, value = parts
      if expiration_secs < 0 or expiration_secs > 21 * 24 * 60 * 60:
        ctx.error('expiration_secs is outside valid range; up to 21 days')
        continue
      if expiration_secs % 60:
        ctx.error('expiration_secs must be a multiple of 60 seconds')
        continue
      expirations.add(expiration_secs)
      _validate_dimension_key(key, known_keys, ctx)
  if len(expirations) >= 6:
    ctx.error('at most 6 different expiration_secs values can be used')


def _validate_relative_path(path, ctx):
  if not path:
    ctx.error('path is required')
  if '\\' in path:
    ctx.error(
        'path cannot contain \\. On Windows forward-slashes will be '
        'replaced with back-slashes.'
    )
  if '..' in path.split('/'):
    ctx.error('path cannot contain ".."')
  if path.startswith('/'):
    ctx.error('path cannot start with "/"')


def _validate_recipe_cfg(recipe, ctx, final=True):
  """Validates a Recipe message.

  If final is False, does not validate for completeness.
  """
  if final:
    if not recipe.name:
      ctx.error('name unspecified')
    repo = clear_dash(recipe.repository)
    if recipe.cipd_package and repo:
      ctx.error('specify either cipd_package or repository, not both')
    if not recipe.cipd_package and not repo:
      ctx.error('specify either cipd_package or repository')
  validate_recipe_properties(recipe.properties, recipe.properties_j, ctx)


def validate_recipe_property(key, value, ctx):
  if not key:
    ctx.error('key not specified')
  elif key == 'buildbucket':
    ctx.error('reserved property')
  elif key == '$recipe_engine/runtime':
    if not isinstance(value, dict):
      ctx.error('not a JSON object')
    else:
      for k in ('is_luci', 'is_experimental'):
        if k in value:
          ctx.error('key %r: reserved key', k)


def validate_recipe_properties(properties, properties_j, ctx):
  keys = set()

  def validate(props, is_json):
    for p in props:
      with ctx.prefix('%r: ', p):
        if ':' not in p:
          ctx.error('does not have a colon')
          continue

        key, value = p.split(':', 1)
        if is_json:
          try:
            value = json.loads(value)
          except ValueError as ex:
            ctx.error('%s', ex)
            continue

        validate_recipe_property(key, value, ctx)
        if key in keys:
          ctx.error('duplicate property')
        else:
          keys.add(key)

  with ctx.prefix('properties '):
    validate(properties, False)
  with ctx.prefix('properties_j '):
    validate(properties_j, True)


def validate_builder_cfg(builder, mixin_names, final, ctx):
  """Validates a Builder message.

  Does not apply mixins, only checks that a referenced mixin exists.

  If final is False, does not validate for completeness.
  """
  if final and not builder.name:
    ctx.error('name unspecified')
  else:
    invalid_chars = ''.join(
        sorted(
            set(
                c for c in builder.name if c not in _BUILDER_NAME_VALID_CHAR_SET
            )
        )
    )
    if invalid_chars:
      ctx.error(
          'name uses invalid char(s) %r. Alphabet: "%s"', invalid_chars,
          BUILDER_NAME_VALID_CHARS
      )

  for i, t in enumerate(builder.swarming_tags):
    with ctx.prefix('tag #%d: ', i + 1):
      _validate_tag(t, ctx)

  _validate_dimensions('dimension', builder.dimensions, ctx)

  cache_paths = set()
  cache_names = set()
  fallback_secs = set()
  for i, c in enumerate(builder.caches):
    with ctx.prefix('cache #%d: ', i + 1):
      _validate_cache_entry(c, ctx)
      if c.name:
        if c.name in cache_names:
          ctx.error('duplicate name')
        else:
          cache_names.add(c.name)
      if c.path:
        if c.path in cache_paths:
          ctx.error('duplicate path')
        else:
          cache_paths.add(c.path)
        if c.wait_for_warm_cache_secs:
          if c.wait_for_warm_cache_secs < 60:
            ctx.error('wait_for_warm_cache_secs must be at least 60 seconds')
          elif c.wait_for_warm_cache_secs % 60:
            ctx.error('wait_for_warm_cache_secs must be rounded on 60 seconds')
          fallback_secs.add(c.wait_for_warm_cache_secs)
  if len(fallback_secs) > 7:
    # There can only be 8 task_slices.
    ctx.error(
        'too many different (%d) wait_for_warm_cache_secs values; max 7' %
        len(fallback_secs)
    )

  with ctx.prefix('recipe: '):
    _validate_recipe_cfg(builder.recipe, ctx, final=final)

  if builder.priority > 200:
    ctx.error('priority must be in [0, 200] range; got %d', builder.priority)

  if builder.service_account:
    with ctx.prefix('service_account: '):
      _validate_service_account(builder.service_account, ctx)

  for m in builder.mixins:
    if not m:
      ctx.error('referenced mixin name is empty')
    elif m not in mixin_names:
      ctx.error('mixin "%s" is not defined', m)

  # Limit (expiration+execution) to 47h. See max_grant_validity_duration in
  # https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-token-server/service_accounts.cfg
  if builder.expiration_secs + builder.execution_timeout_secs > 47 * 60 * 60:
    ctx.error('expiration_secs + execution_timeout_secs must be at most 47h')


def _validate_cache_entry(entry, ctx):
  if not entry.name:
    ctx.error('name is required')
  elif not _CACHE_NAME_RE.match(entry.name):
    ctx.error('name "%s" does not match %s', entry.name, _CACHE_NAME_RE.pattern)

  _validate_relative_path(entry.path, ctx)


def validate_builder_mixins(mixins, ctx):
  """Validates mixins.

  Checks that:
  - mixins' attributes have valid values
  - mixins have unique names
  - mixins do not have circular references.
  """
  by_name = {m.name: m for m in mixins}
  seen = set()
  for i, m in enumerate(mixins):
    with ctx.prefix('builder_mixin %s: ' % (m.name or '#%s' % (i + 1))):
      if not m.name:
        # with final=False below, validate_builder_cfg will ignore name.
        ctx.error('name unspecified')
      elif m.name in seen:
        ctx.error('duplicate name')
      else:
        seen.add(m.name)
      validate_builder_cfg(m, by_name, False, ctx)

  # Check circular references.
  circles = set()

  def check_circular(chain):
    mixin = by_name[chain[-1]]
    for sub_name in mixin.mixins:
      if not sub_name or sub_name not in by_name:
        # This may happen if validation above fails.
        # We've already reported this, so ignore here.
        continue
      try:
        recurrence = chain.index(sub_name)
      except ValueError:
        recurrence = -1
      if recurrence >= 0:
        circle = chain[recurrence:]

        # make circle deterministic
        smallest = circle.index(min(circle))
        circle = circle[smallest:] + circle[:smallest]

        circles.add(tuple(circle))
        continue

      chain.append(sub_name)
      try:
        check_circular(chain)
      finally:
        chain.pop()

  for name in by_name:
    check_circular([name])
  for circle in sorted(circles):
    circle = list(circle) + [circle[0]]
    ctx.error('circular mixin chain: %s', ' -> '.join(circle))


def validate_project_cfg(swarming, mixins, mixins_are_valid, ctx):
  """Validates a project_config_pb2.Swarming message.

  Args:
    swarming (project_config_pb2.Swarming): the config to validate.
    mixins (dict): {mixin_name: mixin}, builder mixins that may be used by
      builders.
    mixins_are_valid (bool): if True, mixins are valid.
  """

  def make_subctx():
    return validation.Context(
        on_message=lambda msg: ctx.msg(msg.severity, '%s', msg.text)
    )

  with ctx.prefix('hostname: '):
    _validate_hostname(swarming.hostname, ctx)

  if swarming.task_template_canary_percentage.value > 100:
    ctx.error('task_template_canary_percentage.value must must be in [0, 100]')

  should_try_merge = mixins_are_valid
  if swarming.HasField('builder_defaults'):
    with ctx.prefix('builder_defaults: '):
      if swarming.builder_defaults.name:
        ctx.error('do not specify default name')
      subctx = make_subctx()
      validate_builder_cfg(swarming.builder_defaults, mixins, False, subctx)
      if subctx.result().has_errors:
        should_try_merge = False

  seen = set()
  for i, b in enumerate(swarming.builders):
    with ctx.prefix('builder %s: ' % (b.name or '#%s' % (i + 1))):
      # Validate b before merging, otherwise merging will fail.
      subctx = make_subctx()
      validate_builder_cfg(b, mixins, False, subctx)
      if subctx.result().has_errors or not should_try_merge:
        # Do no try to merge invalid configs.
        continue

      merged = copy.deepcopy(b)
      flatten_swarmingcfg.flatten_builder(
          merged, swarming.builder_defaults, mixins
      )
      if merged.name in seen:
        ctx.error('duplicate builder name')
      else:
        seen.add(merged.name)
      validate_builder_cfg(merged, mixins, True, ctx)


def validate_service_cfg(swarming, ctx):
  if swarming.milo_hostname:
    with ctx.prefix('milo_hostname: '):
      _validate_hostname(swarming.milo_hostname, ctx)


def clear_dash(s):
  """Returns s if it is not '-', otherwise returns ''."""
  if s == '-':
    return ''
  return s
