# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


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
      key, value = components
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
      if not value:
        ctx.error('no value')


def validate_recipe_cfg(recipe, ctx):
  if not recipe.name:
    ctx.error('name unspecified')
  if not recipe.repository:
    ctx.error('repository unspecified')
  for i, p in enumerate(recipe.properties):
    with ctx.prefix('property #%d: ', i + 1):
      if ':' not in p:
        ctx.error('does not have colon')
      else:
        key, _ = p.split(':', 1)
        if not key:
          ctx.error('key not specified')
        elif key =='buildername':
          ctx.error(
            'do not specify buildername property; '
            'it is added by swarmbucket automatically')


def validate_builder_cfg(builder, ctx, bucket_has_pool_dim=False):
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

  if not builder.HasField('recipe'):
    ctx.error('recipe unspecified')
  else:
    with ctx.prefix('recipe: '):
      validate_recipe_cfg(builder.recipe, ctx)

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

  for i, b in enumerate(swarming.builders):
    with ctx.prefix('builder %s: ' % (b.name or '#%s' % (i + 1))):
      validate_builder_cfg(b, ctx, bucket_has_pool_dim=has_pool_dim)

def has_pool_dimension(dimensions):
  return any(d.startswith('pool:') for d in dimensions)
