# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import re

from components.config import validation

from proto import project_config_pb2


DIMENSION_KEY_RGX = re.compile(r'^[a-zA-Z\_\-]+$')
# Copied from
# https://github.com/luci/luci-py/blob/75de6021b50a73e140eacfb80760f8c25aa183ff/appengine/swarming/server/task_request.py#L101
# Keep it synchronized.
CACHE_NAME_RE = re.compile(ur'^[a-z0-9_]{1,4096}$')


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
  return ['%s:%s' % (k, v) for k, v in sorted(dims.iteritems()) if v]


def merge_builder(b1, b2):
  """Merges Builder message b2 into b1. Expects messages to be valid."""
  dims = merge_dimensions(b1.dimensions, b2.dimensions)
  recipe = None
  if b1.HasField('recipe') or b2.HasField('recipe'):  # pragma: no branch
    recipe = copy.deepcopy(b1.recipe)
    merge_recipe(recipe, b2.recipe)

  b1.MergeFrom(b2)
  b1.dimensions[:] = dims
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


def validate_recipe_properties(properties, properties_j, ctx):
  keys = set()

  def validate_key(key):
    if not key:
      ctx.error('key not specified')
    elif key =='buildername':
      ctx.error(
          'do not specify buildername property; '
          'it is added by swarmbucket automatically')
    if key in keys:
      ctx.error('duplicate property "%s"', key)

  for i, p in enumerate(properties):
    with ctx.prefix('properties #%d: ', i + 1):
      if ':' not in p:
        ctx.error('does not have colon')
      else:
        key, _ = p.split(':', 1)
        validate_key(key)
        keys.add(key)

  for i, p in enumerate(properties_j):
    with ctx.prefix('properties_j #%d: ', i + 1):
      if ':' not in p:
        ctx.error('does not have colon')
      else:
        key, value = p.split(':', 1)
        validate_key(key)
        keys.add(key)
        try:
          json.loads(value)
        except ValueError as ex:
          ctx.error(ex)


def validate_builder_cfg(builder, ctx, final=True):
  """Validates a Builder message.

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


def validate_cache_entry(entry, ctx):
  if not entry.name:
    ctx.error('name is required')
  elif not CACHE_NAME_RE.match(entry.name):
    ctx.error('name "%s" does not match %s', entry.name, CACHE_NAME_RE.pattern)

  validate_relative_path(entry.path, ctx)


def validate_cfg(swarming, ctx):
  def make_subctx():
    return validation.Context(
        on_message=lambda msg: ctx.msg(msg.severity, '%s', msg.text))

  if not swarming.hostname:
    ctx.error('hostname unspecified')
  if swarming.task_template_canary_percentage.value > 100:
    ctx.error('task_template_canary_percentage.value must must be in [0, 100]')

  with ctx.prefix('builder_defaults: '):
    if swarming.builder_defaults.name:
      ctx.error('do not specify default name')
    subctx = make_subctx()
    validate_builder_cfg(swarming.builder_defaults, subctx, final=False)
    builder_defaults_has_errors = subctx.result().has_errors

  for i, b in enumerate(swarming.builders):
    with ctx.prefix('builder %s: ' % (b.name or '#%s' % (i + 1))):
      # Validate b before merging, otherwise merging will fail.
      subctx = make_subctx()
      validate_builder_cfg(b, subctx, final=False)
      if subctx.result().has_errors or builder_defaults_has_errors:
        # Do no try to merge invalid configs.
        continue

      merged = copy.deepcopy(swarming.builder_defaults)
      merge_builder(merged, b)
      validate_builder_cfg(merged, ctx)


def has_pool_dimension(dimensions):
  return any(d.startswith('pool:') for d in dimensions)
