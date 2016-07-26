# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import re

from proto import project_config_pb2


DIMENSION_KEY_RGX = re.compile(r'^[a-zA-Z\_\-]+$')


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


def validate_recipe_cfg(recipe, common_recipe, ctx):
  common_recipe = common_recipe or project_config_pb2.Swarming.Recipe()
  if not (recipe.name or common_recipe.name):
    ctx.error('name unspecified')
  if not (recipe.repository or common_recipe.repository):
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


def validate_builder_cfg(
    builder, ctx, bucket_has_pool_dim=False, common_recipe=None):
  if not builder.name:
    ctx.error('name unspecified')

  for i, t in enumerate(builder.swarming_tags):
    with ctx.prefix('tag #%d: ', i + 1):
      validate_tag(t, ctx)

  validate_dimensions('dimension', builder.dimensions, ctx)
  if not bucket_has_pool_dim and not has_pool_dimension(builder.dimensions):
    ctx.error(
      'has no "pool" dimension. '
      'Either define it in the builder or in "common_dimensions"')

  if not builder.HasField('recipe') and not common_recipe:
    ctx.error('recipe unspecified')
  else:
    with ctx.prefix('recipe: '):
      validate_recipe_cfg(builder.recipe, common_recipe, ctx)

  if builder.priority < 0 or builder.priority > 200:
    ctx.error('priority must be in [0, 200] range; got %d', builder.priority)


def validate_cfg(swarming, ctx):
  if not swarming.hostname:
    ctx.error('hostname unspecified')
  for i, t in enumerate(swarming.common_swarming_tags):
    with ctx.prefix('common tag #%d: ', i + 1):
      validate_tag(t, ctx)

  validate_dimensions('common dimension', swarming.common_dimensions, ctx)
  has_pool_dim = has_pool_dimension(swarming.common_dimensions)
  common_recipe = None
  if swarming.HasField('common_recipe'):
    common_recipe = swarming.common_recipe
    with ctx.prefix('common_recipe: '):
      validate_recipe_properties(
          swarming.common_recipe.properties,
          swarming.common_recipe.properties_j, ctx)

  for i, b in enumerate(swarming.builders):
    with ctx.prefix('builder %s: ' % (b.name or '#%s' % (i + 1))):
      validate_builder_cfg(
          b, ctx, bucket_has_pool_dim=has_pool_dim,
          common_recipe=common_recipe)


def has_pool_dimension(dimensions):
  return any(d.startswith('pool:') for d in dimensions)
