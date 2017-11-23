# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=line-too-long

import copy
import json
import re

from components.config import validation


DIMENSION_KEY_RGX = re.compile(r'^[a-zA-Z\_\-]+$')
# Copied from
# https://github.com/luci/luci-py/blob/75de6021b50a73e140eacfb80760f8c25aa183ff/appengine/swarming/server/task_request.py#L101
# Keep it synchronized.
CACHE_NAME_RE = re.compile(ur'^[a-z0-9_]{1,4096}$')
# See https://chromium.googlesource.com/infra/luci/luci-py/+/master/appengine/swarming/server/service_accounts.py
SERVICE_ACCOUNT_RE = re.compile(r'^[0-9a-zA-Z_\-\.\+\%]+@[0-9a-zA-Z_\-\.]+$')


def validate_hostname(hostname, ctx):
  if not hostname:
    ctx.error('unspecified')
  if '://' in hostname:
    ctx.error('must not contain "://"')


def validate_service_account(service_account, ctx):
  if service_account != 'bot' and not SERVICE_ACCOUNT_RE.match(service_account):
    ctx.error(
        'value "%s" does not match %s',
        service_account, SERVICE_ACCOUNT_RE.pattern)


def read_properties(recipe):
  """Parses build properties from the recipe message.

  Expects the message to be valid.

  Uses NO_PROPERTY for empty values.
  """
  result = dict(p.split(':', 1) for p in recipe.properties)
  for p in recipe.properties_j:
    k, v = p.split(':', 1)
    parsed = json.loads(v)
    result[k] = parsed
  return result


def merge_recipe(r1, r2):
  """Merges Recipe message r2 into r1.

  Expects messages to be valid.

  All properties are converted to properties_j.
  """
  props = read_properties(r1)
  props.update(read_properties(r2))

  r1.MergeFrom(r2)
  r1.properties[:] = []
  r1.properties_j[:] = [
    '%s:%s' % (k, json.dumps(v))
    for k, v in sorted(props.iteritems())
    if v is not None
  ]


def merge_dimensions(d1, d2):
  """Merges dimensions. Values in d2 overwrite values in d1.

  Expects dimensions to be valid.

  If a dimensions value in d2 is empty, it is excluded from the result.
  """
  parse = lambda d: dict(a.split(':', 1) for a in d)
  dims = parse(d1)
  dims.update(parse(d2))
  return sorted('%s:%s' % (k, v) for k, v in dims.iteritems() if v)


def merge_builder(b1, b2):
  """Merges Builder message b2 into b1. Expects messages to be valid."""
  assert not b2.mixins, 'do not merge unflattened builders'
  dims = merge_dimensions(b1.dimensions, b2.dimensions)
  recipe = None
  if b1.HasField('recipe') or b2.HasField('recipe'):  # pragma: no branch
    recipe = copy.deepcopy(b1.recipe)
    merge_recipe(recipe, b2.recipe)

  b1.MergeFrom(b2)
  b1.dimensions[:] = dims
  b1.swarming_tags[:] = sorted(set(b1.swarming_tags))

  caches = [
    t[1]
    for t in sorted({c.name: c for c in b1.caches}.iteritems())
  ]
  del b1.caches[:]
  b1.caches.extend(caches)

  if recipe:  # pragma: no branch
    b1.recipe.CopyFrom(recipe)


def validate_tag(tag, ctx):
  # a valid swarming tag is a string that contains ":"
  if ':' not in tag:
    ctx.error('does not have ":": %s', tag)
  name = tag.split(':', 1)[0]
  if name.lower() == 'builder':
    ctx.error(
        'do not specify builder tag; '
        'it is added by swarmbucket automatically')


def validate_dimensions(field_name, dimensions, ctx):
  known_keys = set()
  for i, dim in enumerate(dimensions):
    with ctx.prefix('%s #%d: ', field_name, i + 1):
      components = dim.split(':', 1)
      if len(components) != 2:
        ctx.error('does not have ":"')
        continue
      key, _ = components
      if not key:
        ctx.error('no key')
      else:
        if not DIMENSION_KEY_RGX.match(key):
          ctx.error(
            'key "%s" does not match pattern "%s"',
            key, DIMENSION_KEY_RGX.pattern)
        if key in known_keys:
          ctx.error('duplicate key %s', key)
        else:
          known_keys.add(key)


def validate_relative_path(path, ctx):
  if not path:
    ctx.error('path is required')
  if '\\' in path:
    ctx.error(
        'path cannot contain \\. On Windows forward-slashes will be '
        'replaced with back-slashes.')
  if '..' in path.split('/'):
    ctx.error('path cannot contain ".."')
  if path.startswith('/'):
    ctx.error('path cannot start with "/"')


def validate_recipe_cfg(recipe, ctx, final=True):
  """Validates a Recipe message.

  If final is False, does not validate for completeness.
  """
  if final and not recipe.name:
    ctx.error('name unspecified')
  if final and not recipe.repository:
    ctx.error('repository unspecified')
  validate_recipe_properties(recipe.properties, recipe.properties_j, ctx)


def validate_recipe_property(key, value, ctx):
  if not key:
    ctx.error('key not specified')
  elif key in {'buildername', 'buildbucket'}:
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
            ctx.error(ex)
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

  for i, t in enumerate(builder.swarming_tags):
    with ctx.prefix('tag #%d: ', i + 1):
      validate_tag(t, ctx)

  validate_dimensions('dimension', builder.dimensions, ctx)
  if final and not has_pool_dimension(builder.dimensions):
    ctx.error('has no "pool" dimension')

  cache_paths = set()
  cache_names = set()
  for i, c in enumerate(builder.caches):
    with ctx.prefix('cache #%d: ', i + 1):
      validate_cache_entry(c, ctx)
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

  with ctx.prefix('recipe: '):
    validate_recipe_cfg(builder.recipe, ctx, final=final)

  if builder.priority > 200:
    ctx.error('priority must be in [0, 200] range; got %d', builder.priority)

  if builder.service_account:
    with ctx.prefix('service_account: '):
      validate_service_account(builder.service_account, ctx)

  for m in builder.mixins:
    if not m:
      ctx.error('referenced mixin name is empty')
    elif m not in mixin_names:
      ctx.error('mixin "%s" is not defined', m)


def validate_cache_entry(entry, ctx):
  if not entry.name:
    ctx.error('name is required')
  elif not CACHE_NAME_RE.match(entry.name):
    ctx.error('name "%s" does not match %s', entry.name, CACHE_NAME_RE.pattern)

  validate_relative_path(entry.path, ctx)


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
        on_message=lambda msg: ctx.msg(msg.severity, '%s', msg.text))

  if swarming.hostname:
    with ctx.prefix('hostname: '):
      validate_hostname(swarming.hostname, ctx)

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

  for i, b in enumerate(swarming.builders):
    with ctx.prefix('builder %s: ' % (b.name or '#%s' % (i + 1))):
      # Validate b before merging, otherwise merging will fail.
      subctx = make_subctx()
      validate_builder_cfg(b, mixins, False, subctx)
      if subctx.result().has_errors or not should_try_merge:
        # Do no try to merge invalid configs.
        continue

      merged = copy.deepcopy(b)
      flatten_builder(merged, swarming.builder_defaults, mixins)
      validate_builder_cfg(merged, mixins, True, ctx)


def has_pool_dimension(dimensions):
  return any(d.startswith('pool:') for d in dimensions)


def flatten_builder(builder, defaults, mixins):
  """Inlines defaults or mixins into the builder.

  Applies defaults, then mixins and then reapplies values defined in |builder|.
  Flattenes defaults and referenced mixins recursively.

  This operation is NOT idempotent if defaults!=None.

  Args:
    builder (project_config_pb2.Builder): the builder to flatten.
    defaults (project_config_pb2.Builder): builder defaults.
      May use mixins.
    mixins ({str: project_config_pb2.Builder} dict): a map of mixin names
      that can be inlined. All referenced mixins must be in this dict.
      Applied after defaults.
  """
  if not defaults and not builder.mixins:
    return
  orig_mixins = builder.mixins
  builder.ClearField('mixins')
  orig_without_mixins = copy.deepcopy(builder)
  if defaults:
    flatten_builder(defaults, None, mixins)
    merge_builder(builder, defaults)
  for m in orig_mixins:
    flatten_builder(mixins[m], None, mixins)
    merge_builder(builder, mixins[m])
  merge_builder(builder, orig_without_mixins)


def validate_service_cfg(swarming, ctx):
  with ctx.prefix('default_hostname: '):
    validate_hostname(swarming.default_hostname, ctx)
  if swarming.milo_hostname:
    with ctx.prefix('milo_hostname: '):
      validate_hostname(swarming.milo_hostname, ctx)
